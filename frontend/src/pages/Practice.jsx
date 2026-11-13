import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Button, Spinner, Modal } from 'react-bootstrap';
import { useLocation, useNavigate } from "react-router-dom";
import CameraRecorder from '../components/CameraHandlers/CameraRecorder';
import { postDanceAttempt, getVideoAnalysis, getDanceAttemptStatus } from "../api/calls";

export default function Practice() {
    const navigate = useNavigate();
    const location = useLocation();

    const referenceVideoRef = useRef(null);
    const cameraRecorderRef = useRef(null);
    const feedbackOverlayRef = useRef(null);
    const lastFeedbackTextRef = useRef("");
    const localVideoUrlRef = useRef(null);

    // Camera states
    const [isCameraReady, setIsCameraReady] = useState(false);
    const [cameraError, setCameraError] = useState(null);

    const [practiceState, setState] = useState('idle');
    const practiceStateRef = useRef(practiceState);
    const [countdown, setCountdown] = useState(3);

    const [referenceAnalysis, setReferenceAnalysis] = useState(null);

    // States for asynchronous processing
    const [taskId, setTaskId] = useState(null);

    const currentVideo = location.state?.currentVideo;

    // State tracker
    useEffect(() => {
        practiceStateRef.current = practiceState;
    }, [practiceState]);

    // Fetch analysis json for the video
    useEffect(() => {
        if (currentVideo?.id) {
            getVideoAnalysis(currentVideo.id)
                .then(data => setReferenceAnalysis(data))
                .catch(err => console.error("Failed to load reference analysis", err));
        }
    }, [currentVideo?.id]);

    // Practice countdown
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

    // Polling loop for backend processing
    useEffect(() => {
        let pollInterval;

        if (practiceState === 'processing' && taskId) {
            pollInterval = setInterval(async () => {
                try {
                    const result = await getDanceAttemptStatus(taskId);

                    if (result && result.status === 'completed') {
                        clearInterval(pollInterval);

                        // Navigate to the new page and inject the data to prevent another API call
                        navigate(`/score/${result.data.attempt_id}`, {
                            state: {
                                scoreData: result.data,
                                localVideoUrl: localVideoUrlRef.current
                            }
                        });
                    } else if (result && result.status === 'failed') {
                        clearInterval(pollInterval);
                        console.error("Backend processing failed");
                        setState('idle');
                    }
                } catch (error) {
                    console.error("Error polling score:", error);
                }
            }, 2000); // Poll every 2 seconds
        }

        return () => {
            if (pollInterval) clearInterval(pollInterval);
        };
    }, [practiceState, taskId, navigate]);

    const handleStartPractice = () => {
        setCountdown(3);
        setState('positioning');
    };

    // Camera and recording handlers
    const handleCameraReady = useCallback(() => {
        setIsCameraReady(true);
        setCameraError(null);
    }, []);

    const handleCameraError = useCallback((error) => {
        setCameraError(error);
    }, []);

    // Frame analysis handler
    const handleFrameAnalyzed = useCallback((liveFrameData) => {
        if (practiceStateRef.current === 'positioning' && liveFrameData.isFullyVisible) {
            setState('countdown');
            return;
        }

        if (practiceStateRef.current === 'recording' && feedbackOverlayRef.current) {
            // Placeholder. TODO: Implement scoring

            const totalVelocity = liveFrameData.joints ? Object.values(liveFrameData.joints).reduce(
                (sum, j) => sum + Math.abs(j.angular_velocity), 0
            ) : 0;

            let newFeedback = "";
            if (totalVelocity > 300) newFeedback = "Perfect!";
            else if (totalVelocity > 150) newFeedback = "Great!";
            else if (totalVelocity > 50) newFeedback = "Good";

            if (newFeedback !== lastFeedbackTextRef.current) {
                lastFeedbackTextRef.current = newFeedback;
                feedbackOverlayRef.current.innerText = newFeedback;
                feedbackOverlayRef.current.className = `display-4 fw-bold text-white text-uppercase text-shadow ${newFeedback ? 'bounce-animation' : ''}`;
            }
        }
    }, []);

    // End recording and feedback when video ends
    const handleReferenceVideoEnded = () => {
        setState('processing');
        if (cameraRecorderRef.current) cameraRecorderRef.current.stopRecording();
        if (feedbackOverlayRef.current) feedbackOverlayRef.current.innerText = "";
    };

    // Submit attempt and await task ID
    const handleRecordingSubmission = useCallback(async ({ frames, videoBlob }) => {
    if (!currentVideo?.id) return;
    try {
        // Create a local browser URL for the video so the score page can play it
        localVideoUrlRef.current = URL.createObjectURL(videoBlob);

        const response = await postDanceAttempt(currentVideo.id, frames, videoBlob);

        if (response.task_id) {
            setTaskId(response.task_id);
        } else {
            navigate(`/score/${response.id}`, {
                state: {
                    scoreData: response,
                    localVideoUrl: localVideoUrlRef.current
                }
            });
        }
    } catch (error) {
        console.error("Failed to submit practice attempt:", error);
        setState('idle');
    }
}, [currentVideo?.id, navigate]);

    if (!currentVideo) {
        return <div className="p-5 text-danger">Video not found!</div>;
    }
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
                    <h5 className="mb-4">Get into position!</h5>
                    <Button
                        variant="primary"
                        size="lg"
                        className="px-5 rounded-pill shadow-sm"
                        onClick={handleStartPractice}
                        disabled={!isCameraReady || !referenceAnalysis}
                    >
                        {cameraError ? (
                            <span className="text-danger">Camera unavailable. Check permissions.</span>
                        ) : isCameraReady && referenceAnalysis ? (
                            'Start Practice'
                        ) : (
                            <>
                                <Spinner size="sm" className="me-2"/>
                                {isCameraReady ? 'Loading Analysis...' : 'Initializing Camera...'}
                            </>
                        )}
                    </Button>
                </Modal.Body>
                <Modal.Footer className="border-0 justify-content-center pb-4">
                    <Button variant="link" className="text-secondary text-decoration-none" onClick={() => navigate('/')}>
                        Cancel & go back
                    </Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}