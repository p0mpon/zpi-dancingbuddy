import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Button, Spinner, Modal } from 'react-bootstrap';
import { useLocation, useNavigate } from "react-router-dom";
import CameraRecorder from '../components/CameraHandlers/CameraRecorder';
import {postDanceAttempt, getVideoAnalysis, getDanceAttemptStatus, getFullVideo, getVideoDetails} from "../api/calls";
import { compareLiveFrames } from '../components/CameraHandlers/LiveScoring';

// Adjust this value to change how long the "Perfect! / Great!" text stays on screen (in milliseconds)
const FEEDBACK_COOLDOWN_MS = 800;

export default function Practice() {
    const navigate = useNavigate();
    const location = useLocation();

    const referenceVideoRef = useRef(null);
    const cameraRecorderRef = useRef(null);
    const feedbackOverlayRef = useRef(null);
    const localVideoUrlRef = useRef(null);

    // Sliding window buffer refs
    const liveFrameBufferRef = useRef([]);
    const nextChoreoIndexRef = useRef(0);

    // Accumulators for averaging scores & UI throttling
    const intervalScoreSumRef = useRef(0);
    const intervalFrameCountRef = useRef(0);
    const feedbackCooldownRef = useRef(false);
    const feedbackTimeoutRef = useRef(null);

    // Debug Tracker (Invisible to user, highly useful for your next branch)
    const debugLossAccumulatorRef = useRef({ angle: 0, velocity: 0, acceleration: 0, hipHeight: 0, hipRotation: 0 });

    const [isCameraReady, setIsCameraReady] = useState(false);
    const [cameraError, setCameraError] = useState(null);
    const [statusError, setStatusError] = useState(null);

    const [practiceState, setState] = useState('idle');
    const practiceStateRef = useRef(practiceState);
    const [countdown, setCountdown] = useState(3);

    const [referenceAnalysis, setReferenceAnalysis] = useState(null);
    const [taskId, setTaskId] = useState(null);

    const [currentVideo, setCurrentVideo] = useState(location.state?.currentVideo || null);

    useEffect(() => {
        practiceStateRef.current = practiceState;
    }, [practiceState]);

    useEffect(() => {
        if (!currentVideo?.id) return;
        let isSubscribed = true;
        let timeoutId;

        const loadVideoAndCheckStatus = async () => {
            try {
                const fullVideo = await getFullVideo(currentVideo.id);
                if (!isSubscribed) return;

                setCurrentVideo(fullVideo);
                await evaluateStatus(fullVideo.analysis_status);
            } catch (err) {
                console.error("Failed to load full video", err);
                if (isSubscribed) setStatusError("Failed to load video file.");
            }
        };

        const evaluateStatus = async (status) => {
            const currentStatus = status?.toLowerCase();

            if (currentStatus === 'done') {
                try {
                    const data = await getVideoAnalysis(currentVideo.id);
                    if (isSubscribed) setReferenceAnalysis(data);
                } catch (err) {
                    console.error("Failed to load reference analysis", err);
                    if (isSubscribed) setStatusError("Failed to download analysis data.");
                }
            } else if (currentStatus === 'processing' || currentStatus === 'pending') {
                timeoutId = setTimeout(pollStatus, 3000);
            } else if (currentStatus === 'failed') {
                if (isSubscribed) setStatusError("Video analysis failed on the server. Cannot practice this video.");
            }
        };

        const pollStatus = async () => {
            try {
                const videoDetails = await getVideoDetails(currentVideo.id);
                if (!isSubscribed) return;

                await evaluateStatus(videoDetails.analysis_status);
            } catch (err) {
                console.error("Failed to fetch video details", err);
                if (isSubscribed) setStatusError("Failed to check video status.");
            }
        };

        loadVideoAndCheckStatus();

        return () => {
            isSubscribed = false;
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, [currentVideo?.id]);

    useEffect(() => {
        let timer;
        if (practiceState === 'countdown' && countdown > 0) {
            timer = setTimeout(() => setCountdown(c => c - 1), 1000);
        } else if (practiceState === 'countdown' && countdown === 0) {
            setState('recording');
            if (cameraRecorderRef.current) cameraRecorderRef.current.startRecording();
            if (referenceVideoRef.current) referenceVideoRef.current.play();
        }
        return () => clearTimeout(timer);
    }, [practiceState, countdown]);

    useEffect(() => {
        let pollInterval;
        if (practiceState === 'processing' && taskId) {
            pollInterval = setInterval(async () => {
                try {
                    const result = await getDanceAttemptStatus(taskId);
                    if (result && result.status === 'completed') {
                        clearInterval(pollInterval);
                        navigate(`/score/${result.data.attempt_id}`, {
                            state: { scoreData: result.data, localVideoUrl: localVideoUrlRef.current }
                        });
                    } else if (result && result.status === 'failed') {
                        clearInterval(pollInterval);
                        console.error("Backend processing failed");
                        setState('idle');
                    }
                } catch (error) {
                    console.error("Error polling score:", error);
                }
            }, 2000);
        }
        return () => { if (pollInterval) clearInterval(pollInterval); };
    }, [practiceState, taskId, navigate]);

    const handleStartPractice = () => {
        setCountdown(3);
        setState('positioning');
        liveFrameBufferRef.current = [];
        nextChoreoIndexRef.current = 0;

        intervalScoreSumRef.current = 0;
        intervalFrameCountRef.current = 0;
        feedbackCooldownRef.current = false;
        if (feedbackTimeoutRef.current) clearTimeout(feedbackTimeoutRef.current);
        if (feedbackOverlayRef.current) feedbackOverlayRef.current.innerText = "";

        debugLossAccumulatorRef.current = { angle: 0, velocity: 0, acceleration: 0, hipHeight: 0, hipRotation: 0 };
    };

    const handleCameraReady = useCallback(() => {
        setIsCameraReady(true);
        setCameraError(null);
    }, []);

    const handleCameraError = useCallback((error) => {
        setCameraError(error);
    }, []);

    const handleFrameAnalyzed = useCallback((liveFrameData) => {
        if (practiceStateRef.current === 'positioning' && liveFrameData.isFullyVisible) {
            setState('countdown');
            return;
        }

        if (practiceStateRef.current === 'recording') {
            liveFrameBufferRef.current.push(liveFrameData);
            const currentTime = referenceVideoRef.current?.currentTime || liveFrameData.timestamp;

            while (liveFrameBufferRef.current.length > 0 && liveFrameBufferRef.current[0].timestamp < currentTime - 1.0) {
                liveFrameBufferRef.current.shift();
            }

            if (referenceAnalysis && nextChoreoIndexRef.current < referenceAnalysis.length) {
                const choreoFrame = referenceAnalysis[nextChoreoIndexRef.current];
                const windowEnd = choreoFrame.timestamp_sec + 0.2;

                if (currentTime > windowEnd) {
                    const framesInWindow = liveFrameBufferRef.current.filter(
                        f => Math.abs(f.timestamp - choreoFrame.timestamp_sec) <= 0.2
                    );

                    let bestScore = -Infinity;
                    let bestBreakdown = null;

                    for (const userFrame of framesInWindow) {
                        const result = compareLiveFrames(choreoFrame, userFrame);
                        if (result.score > bestScore) {
                            bestScore = result.score;
                            bestBreakdown = result.breakdown;
                        }
                    }

                    if (bestScore !== -Infinity) {
                        // Accumulate scores between beats
                        intervalScoreSumRef.current += bestScore;
                        intervalFrameCountRef.current += 1;

                        if (bestBreakdown) {
                            debugLossAccumulatorRef.current.angle += bestBreakdown.angle;
                            debugLossAccumulatorRef.current.velocity += bestBreakdown.velocity;
                            debugLossAccumulatorRef.current.acceleration += bestBreakdown.acceleration;
                            debugLossAccumulatorRef.current.hipHeight += bestBreakdown.hipHeight;
                            debugLossAccumulatorRef.current.hipRotation += bestBreakdown.hipRotation;
                        }

                        if (choreoFrame.audio_context.is_beat || choreoFrame.audio_context.is_onset) {
                            // Only update UI if cooldown is finished
                            if (!feedbackCooldownRef.current && intervalFrameCountRef.current > 0) {
                                const averageScore = intervalScoreSumRef.current / intervalFrameCountRef.current;
                                let newFeedback = "";

                                if (averageScore >= 0.85) newFeedback = "Perfect!";
                                else if (averageScore >= 0.70) newFeedback = "Great!";
                                else if (averageScore >= 0.50) newFeedback = "Good";

                                if (newFeedback !== "" && feedbackOverlayRef.current) {
                                    feedbackOverlayRef.current.innerText = newFeedback;

                                    feedbackOverlayRef.current.classList.remove('bounce-animation');
                                    void feedbackOverlayRef.current.offsetWidth;
                                    feedbackOverlayRef.current.className = `display-4 fw-bold text-white text-uppercase text-shadow bounce-animation`;

                                    feedbackCooldownRef.current = true;

                                    feedbackTimeoutRef.current = setTimeout(() => {
                                        if (feedbackOverlayRef.current) {
                                            feedbackOverlayRef.current.innerText = "";
                                        }
                                        feedbackCooldownRef.current = false;
                                    }, FEEDBACK_COOLDOWN_MS);
                                }
                            }

                            intervalScoreSumRef.current = 0;
                            intervalFrameCountRef.current = 0;
                        }
                    }
                    nextChoreoIndexRef.current++;
                }
            }
        }
    }, [referenceAnalysis]);

    const handleReferenceVideoEnded = () => {
        setState('processing');
        if (cameraRecorderRef.current) cameraRecorderRef.current.stopRecording();
        if (feedbackOverlayRef.current) feedbackOverlayRef.current.innerText = "";
    };

    const handleRecordingSubmission = useCallback(async ({ frames, videoBlob }) => {
        if (!currentVideo?.id) return;

        const losses = debugLossAccumulatorRef.current;
        console.log("========== LIVE SCORING DEBUG REPORT ==========");
        console.table(losses);
        const totalLoss = Object.values(losses).reduce((sum, val) => sum + val, 0);
        if (totalLoss > 0) {
            const maxLossParam = Object.keys(losses).reduce((a, b) => losses[a] > losses[b] ? a : b);
            console.log(`❌ BIGGEST SCORE KILLER: ${maxLossParam.toUpperCase()} (Total points lost: ${losses[maxLossParam].toFixed(2)})`);
        }
        console.log("===============================================");

        try {
            localVideoUrlRef.current = URL.createObjectURL(videoBlob);
            const response = await postDanceAttempt(currentVideo.id, frames, videoBlob);
            if (response.task_id) {
                setTaskId(response.task_id);
            } else {
                navigate(`/score/${response.id}`, {
                    state: { scoreData: response, localVideoUrl: localVideoUrlRef.current }
                });
            }
        } catch (error) {
            console.error("Failed to submit practice attempt:", error);
            setState('idle');
        }
    }, [currentVideo?.id, navigate]);

    if (!currentVideo) return <div className="p-5 text-danger">Video not found!</div>;

    return (
        <div className="position-relative w-100 bg-black overflow-hidden rounded-bottom-4" style={{ height: '100vh' }}>
            <video
                ref={referenceVideoRef}
                src={currentVideo.file}
                poster={currentVideo.thumbnail}
                className="w-100 h-100 object-fit-contain"
                onEnded={handleReferenceVideoEnded}
                playsInline
            />

            {practiceState === 'recording' && (
                <div className="position-absolute top-0 start-50 translate-middle-x mt-5 z-3">
                    <span ref={feedbackOverlayRef} style={{ textShadow: '0 4px 10px rgba(0,0,0,0.8)' }} />
                </div>
            )}

            <div className="position-absolute top-0 end-0 m-4 z-2" style={{ width: '320px', maxWidth: '30vw' }}>
                <CameraRecorder
                    ref={cameraRecorderRef}
                    onCameraReady={handleCameraReady}
                    onCameraError={handleCameraError}
                    onFrameAnalyzed={handleFrameAnalyzed}
                    onRecordingComplete={handleRecordingSubmission}
                />
            </div>

            {practiceState === 'positioning' && (
                <div className="position-absolute top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center bg-dark bg-opacity-75 z-3">
                    <h2 className="display-4 fw-bold text-white text-center px-4" style={{ textShadow: '0 4px 15px rgba(0,0,0,0.9)' }}>
                        Step back! <br/>
                        <span className="text-warning fs-3">Get your full body in frame to begin.</span>
                    </h2>
                </div>
            )}

            {practiceState === 'countdown' && (
                <div className="position-absolute top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center bg-dark bg-opacity-50 z-3">
                    <h1 className="display-1 text-white fw-bold" style={{ fontSize: '10rem', textShadow: '0 4px 20px rgba(0,0,0,0.8)' }}>
                        {countdown > 0 ? countdown : 'GO!'}
                    </h1>
                </div>
            )}

            {practiceState === 'processing' && (
                <div className="position-absolute top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center bg-dark bg-opacity-75 z-3">
                    <div className="text-center text-white">
                        <Spinner animation="border" style={{ width: '5rem', height: '5rem' }} className="mb-4 text-primary" />
                        <h2 className="fw-bold">Processing your dance...</h2>
                    </div>
                </div>
            )}

            <Modal
                show={practiceState === 'idle'}
                backdrop="static"
                keyboard={false}
                centered
                contentClassName="bg-black text-light border border-secondary rounded-4 shadow-lg"
            >
                <Modal.Header>
                    <Modal.Title className="fw-bold">{currentVideo.title}</Modal.Title>
                </Modal.Header>
                <Modal.Body className="text-center py-5">
                    {statusError ? (
                        <div className="alert alert-danger mb-4 text-start" style={{ fontSize: '0.9rem' }}>
                            <strong>Error:</strong> <br/>
                            {statusError}
                        </div>
                    ) : (
                        <h5 className="mb-4">Get into position!</h5>
                    )}

                    <Button
                        variant="primary"
                        size="lg"
                        className="px-5 rounded-pill shadow-sm"
                        onClick={handleStartPractice}
                        disabled={!isCameraReady || !referenceAnalysis || statusError}
                    >
                        {cameraError ? (
                            <span className="text-danger">Camera unavailable. Check permissions.</span>
                        ) : isCameraReady && referenceAnalysis ? (
                            'Start Practice'
                        ) : (
                            <>
                                <Spinner size="sm" className="me-2"/>
                                {isCameraReady ? 'Analyzing video on server...' : 'Initializing Camera...'}
                            </>
                        )}
                    </Button>
                </Modal.Body>
                <Modal.Footer className="border-0 justify-content-center pb-4">
                    <Button variant="link" className="text-secondary text-decoration-none" onClick={() => navigate(-1)}>
                        Cancel & go back
                    </Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}