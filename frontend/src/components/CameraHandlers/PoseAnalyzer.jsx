import { useCallback, useEffect, useRef, useState } from 'react';
import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision';

const MODEL_ASSET_URL =
    'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';
const WASM_PATH = '/mediapipe/wasm';
const TARGET_FPS = 30;
const EMA_ALPHA = 0.4;

const JOINT_CONFIG = {
    r_elbow: [12, 14, 16],
    l_elbow: [11, 13, 15],
    r_shoulder: [24, 12, 14],
    l_shoulder: [23, 11, 13],
    r_hip: [12, 24, 26],
    l_hip: [11, 23, 25],
    r_knee: [24, 26, 28],
    l_knee: [23, 25, 27],
    r_ankle: [26, 28, 32],
    l_ankle: [25, 27, 31],
    r_torso: [11, 12, 24],
    l_torso: [12, 11, 23],
};

const round = (value, decimals) => Number(value.toFixed(decimals));

function calculateAngle(a, b, c) {
    const ba = [a.x - b.x, a.y - b.y, a.z - b.z];
    const bc = [c.x - b.x, c.y - b.y, c.z - b.z];
    const baLength = Math.hypot(...ba);
    const bcLength = Math.hypot(...bc);
    if (!baLength || !bcLength) return 0;

    const cosine = ba.reduce((sum, value, index) => sum + value * bc[index], 0) /
        (baLength * bcLength);
    return Math.acos(Math.max(-1, Math.min(1, cosine))) * 180 / Math.PI;
}

export default function usePoseAnalyzer(videoRef, onRecordingComplete, onAnalyzerError, onFrameAnalyzed) {
    const landmarkerRef = useRef(null);
    const animationFrameRef = useRef(null);

    const previewRef = useRef(false);
    const recordingRef = useRef(false);

    const rawPayloadRef = useRef([]);
    const lastValidWorldLandmarksRef = useRef(null);
    const lastValidImageLandmarksRef = useRef(null);

    const previousLiveFrameRef = useRef(null);

    const recordingStartTimeRef = useRef(null);
    const previousFrameTimeRef = useRef(null);

    const onRecordingCompleteRef = useRef(onRecordingComplete);
    const onAnalyzerErrorRef = useRef(onAnalyzerError);
    const onFrameAnalyzedRef = useRef(onFrameAnalyzed);

    const [isReady, setIsReady] = useState(false);
    const [error, setError] = useState(null);

    // Just in case - update refs when callbacks change
    useEffect(() => {
        onRecordingCompleteRef.current = onRecordingComplete;
        onAnalyzerErrorRef.current = onAnalyzerError;
        onFrameAnalyzedRef.current = onFrameAnalyzed;
    }, [onRecordingComplete, onAnalyzerError, onFrameAnalyzed]);

    // Initialize the MediaPipe PoseLandmarker in the background
    useEffect(() => {
        let disposed = false;

        const initialize = async () => {
            try {
                const vision = await FilesetResolver.forVisionTasks(WASM_PATH);
                const landmarker = await PoseLandmarker.createFromOptions(vision, {
                    baseOptions: { modelAssetPath: MODEL_ASSET_URL },
                    runningMode: 'VIDEO',
                    numPoses: 1,
                    minPoseDetectionConfidence: 0.5,
                    minPosePresenceConfidence: 0.5,
                    minTrackingConfidence: 0.5,
                });
                if (disposed) {
                    landmarker.close();
                    return;
                }
                landmarkerRef.current = landmarker;
                setIsReady(true);
            } catch (initializationError) {
                console.error('Failed to initialize camera pose analysis:', initializationError);
                setError(initializationError);
                onAnalyzerErrorRef.current?.(initializationError);
            }
        };

        initialize();
        return () => {
            disposed = true;
            previewRef.current = false;
            recordingRef.current = false;
            if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
            landmarkerRef.current?.close();
            landmarkerRef.current = null;
        };
    }, []);

    const processFrame = useCallback((now) => {
        if (!previewRef.current || !videoRef.current || !landmarkerRef.current) return;
        if (videoRef.current.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
            animationFrameRef.current = requestAnimationFrame(processFrame);
            return;
        }

        const previousTime = previousFrameTimeRef.current;
        if (previousTime === null || now - previousTime >= 1000 / TARGET_FPS) {
            previousFrameTimeRef.current = now;

            const timestamp = recordingRef.current && recordingStartTimeRef.current
                ? round((now - recordingStartTimeRef.current) / 1000, 4)
                : 0;

            const result = landmarkerRef.current.detectForVideo(videoRef.current, now);

            const worldLandmarks = result.worldLandmarks?.[0];
            const imageLandmarks = result.landmarks?.[0];

            if (recordingRef.current && worldLandmarks && imageLandmarks) {
                lastValidWorldLandmarksRef.current = worldLandmarks;
                lastValidImageLandmarksRef.current = imageLandmarks;
            }

            const activeWorld = worldLandmarks || (recordingRef.current ? lastValidWorldLandmarksRef.current : null);
            const activeImage = imageLandmarks || (recordingRef.current ? lastValidImageLandmarksRef.current : null);

            // Forward fill dropped tracking frames with the last known good configuration for the payload
            if (recordingRef.current && activeWorld && activeImage) {
                rawPayloadRef.current.push({
                    timestamp,
                    world_landmarks: activeWorld.map(lm => [lm.x, lm.y, lm.z, lm.visibility ?? 0]),
                    vis_landmarks: activeImage.map(lm => [lm.x, lm.y, lm.z, lm.visibility ?? 0])
                });
            }

            if (worldLandmarks && onFrameAnalyzedRef.current) {
                const previousLiveFrame = previousLiveFrameRef.current;
                const joints = {};
                let visibleJointsCount = 0;

                Object.entries(JOINT_CONFIG).forEach(([name, [aIndex, bIndex, cIndex]]) => {
                    const a = worldLandmarks[aIndex];
                    const b = worldLandmarks[bIndex];
                    const c = worldLandmarks[cIndex];

                    let visibility = 0;
                    let rawAngle = 0;

                    if (a && b && c) {
                        visibility = Math.min(a.visibility ?? 0, b.visibility ?? 0, c.visibility ?? 0);
                        rawAngle = calculateAngle(a, b, c);
                        if (visibility > 0.5) visibleJointsCount++;
                    }

                    const previousJoint = previousLiveFrame?.joints[name];
                    if (!a || !b || !c || visibility < 0.2) {
                        rawAngle = previousJoint ? previousJoint.angle : 0;
                    }

                    const angle = previousJoint
                        ? round((EMA_ALPHA * rawAngle) + ((1 - EMA_ALPHA) * previousJoint.angle), 2)
                        : round(rawAngle, 2);

                    const dt = previousLiveFrame && recordingRef.current ? timestamp - previousLiveFrame.timestamp : 0;

                    const velocity = previousJoint && dt > 0 ? (angle - previousJoint.angle) / dt : 0;
                    const previousVelocity = previousJoint?.angular_velocity ?? 0;

                    const smoothedVelocity = previousJoint
                        ? round((EMA_ALPHA * velocity) + ((1 - EMA_ALPHA) * previousVelocity), 2)
                        : round(velocity, 2);

                    const acceleration = previousJoint && dt > 0 ? round((smoothedVelocity - previousVelocity) / dt, 2) : 0;

                    joints[name] = {
                        angle,
                        angular_velocity: smoothedVelocity,
                        angular_acceleration: acceleration,
                        visibility: round(visibility, 4),
                    };
                });

                const totalConfiguredJoints = Object.keys(JOINT_CONFIG).length;

                // Enforce physical boundary checks for ankles in addition to joint confidence scores
                const leftAnkle2D = activeImage?.[27];
                const rightAnkle2D = activeImage?.[28];
                const anklesOnScreen = leftAnkle2D && rightAnkle2D
                    ? (leftAnkle2D.y < 0.98 && rightAnkle2D.y < 0.98)
                    : false;

                const isFullyVisible = (visibleJointsCount === totalConfiguredJoints) && anklesOnScreen;

                const liveFrameData = { timestamp, joints, isFullyVisible };
                previousLiveFrameRef.current = liveFrameData;

                onFrameAnalyzedRef.current(liveFrameData);
            } else if (!worldLandmarks && onFrameAnalyzedRef.current) {
                onFrameAnalyzedRef.current({ isFullyVisible: false, joints: {} });
            }
        }

        animationFrameRef.current = requestAnimationFrame(processFrame);
    }, [videoRef]);

    // Preview for camera feed for the user to set up
    const startPreview = useCallback(() => {
        if (!videoRef.current || !landmarkerRef.current || !isReady || previewRef.current) return;
        previewRef.current = true;
        animationFrameRef.current = requestAnimationFrame(processFrame);
    }, [isReady, processFrame, videoRef]);

    const stopPreview = useCallback(() => {
        previewRef.current = false;
        if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    }, []);

    // Start recording pose data and video for the user
    const startRecording = useCallback(() => {
        if (!previewRef.current) return;
        rawPayloadRef.current = [];
        previousLiveFrameRef.current = null;
        recordingStartTimeRef.current = performance.now();
        previousFrameTimeRef.current = null;
        recordingRef.current = true;
    }, []);

    const stopRecording = useCallback(() => {
        recordingRef.current = false;

        const payload = [...rawPayloadRef.current];
        rawPayloadRef.current = [];
        lastValidWorldLandmarksRef.current = null;
        lastValidImageLandmarksRef.current = null;
        previousLiveFrameRef.current = null;
        recordingStartTimeRef.current = null;

        onRecordingCompleteRef.current?.(payload);
    }, []);

    return { isReady, error, startPreview, stopPreview, startRecording, stopRecording };
}