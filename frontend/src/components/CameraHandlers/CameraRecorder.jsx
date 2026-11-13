import React, { useEffect, useRef, useState, forwardRef, useImperativeHandle, useCallback } from 'react';
import usePoseAnalyzer from './PoseAnalyzer';

const CameraRecorder = forwardRef(({ onRecordingComplete, onCameraReady, onCameraError, onFrameAnalyzed }, ref) => {
    const videoRef = useRef(null);
    const [isRecording, setIsRecording] = useState(false);
    const [isCameraReady, setIsCameraReady] = useState(false);

    const cameraStreamRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const recordedChunksRef = useRef([]);
    const jsonPayloadRef = useRef(null);

    const handleAnalyzerError = useCallback((error) => onCameraError?.(error), [onCameraError]);

    const checkAndSubmit = useCallback(() => {
        if (jsonPayloadRef.current && recordedChunksRef.current.length > 0) {
            const videoBlob = new Blob(recordedChunksRef.current, { type: 'video/webm' });

            onRecordingComplete?.({
                frames: jsonPayloadRef.current,
                videoBlob
            });

            jsonPayloadRef.current = null;
            recordedChunksRef.current = [];
        }
    }, [onRecordingComplete]);

    const handleAnalyzerComplete = useCallback((payload) => {
        jsonPayloadRef.current = payload;
        checkAndSubmit();
    }, [checkAndSubmit]);

    const { isReady: isAnalyzerReady, startPreview, stopPreview, startRecording: startPoseRecording, stopRecording: stopPoseRecording } = usePoseAnalyzer(
        videoRef,
        handleAnalyzerComplete,
        handleAnalyzerError,
        onFrameAnalyzed
    );

    useImperativeHandle(ref, () => ({
        startRecording: () => {
            if (!isCameraReady || !isAnalyzerReady) return;

            recordedChunksRef.current = [];
            jsonPayloadRef.current = null;

            startPoseRecording();
            if (mediaRecorderRef.current) mediaRecorderRef.current.start();

            setIsRecording(true);
        },
        stopRecording: () => {
            stopPoseRecording();
            if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
                mediaRecorderRef.current.stop();
            }
            setIsRecording(false);
        },
    }), [isAnalyzerReady, isCameraReady, startPoseRecording, stopPoseRecording]);

    useEffect(() => {
        if (isCameraReady && isAnalyzerReady) {
            startPreview();
            onCameraReady?.();
        }
        return () => {
            stopPreview();
        };
    }, [isAnalyzerReady, isCameraReady, onCameraReady, startPreview, stopPreview]);

    useEffect(() => {
        let disposed = false;

        navigator.mediaDevices.getUserMedia({
            video: { width: 1280, height: 720, facingMode: 'user' },
            audio: false,
        }).then(stream => {
            if (disposed) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }
            cameraStreamRef.current = stream;

            try {
                const mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) {
                        recordedChunksRef.current.push(event.data);
                    }
                };
                mediaRecorder.onstop = () => {
                    checkAndSubmit();
                };
                mediaRecorderRef.current = mediaRecorder;
            } catch (e) {
                console.error("MediaRecorder initialization failed:", e);
                onCameraError?.(e);
            }

            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                videoRef.current.onloadeddata = () => setIsCameraReady(true);
            }
        }).catch(error => {
            console.error('Failed to access camera:', error);
            onCameraError?.(error);
        });

        return () => {
            disposed = true;
            cameraStreamRef.current?.getTracks().forEach(track => track.stop());
            cameraStreamRef.current = null;
        };
    }, [onCameraError, checkAndSubmit]);

    return (
        <div className="ratio ratio-16x9 bg-dark rounded-4 overflow-hidden border border-secondary shadow">
            <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className={`w-100 h-100 object-fit-contain ${isRecording ? 'border border-danger border-3' : ''}`}
                style={{ transform: 'scaleX(-1)' }}
            />
        </div>
    );
});

export default CameraRecorder;