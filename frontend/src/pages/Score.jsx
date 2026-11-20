import React, { useEffect, useState, useRef } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { Spinner, Button, Badge } from 'react-bootstrap';
import { getPastDanceAttempt, getDanceAttemptStream, getVideoStream } from '../api/calls';

// Extract the instructor video identifier across possible attempt payload shapes
const extractRefVideoId = (payload) =>
    payload?.reference_video_id ||
    payload?.reference_video?.id ||
    payload?.reference_video ||
    payload?.video_id ||
    payload?.video?.id ||
    payload?.video ||
    null;

// Normalize and sort ScoredFrame entries from score_details
const getScoredFrames = (data) => {
    const rawFrames = Array.isArray(data?.score_details)
        ? data.score_details
        : Array.isArray(data?.score_details?.frames)
          ? data.score_details.frames
          : Array.isArray(data?.frames)
            ? data.frames
            : [];

    return rawFrames
        .filter((f) => Number.isFinite(Number(f?.timestamp_sec)))
        .map((f) => ({
            ...f,
            timestamp_sec: Number(f.timestamp_sec),
        }))
        .sort((a, b) => a.timestamp_sec - b.timestamp_sec);
};

const waitForSeeked = (videoEl, timeoutMs = 400) =>
    new Promise((resolve) => {
        if (!videoEl) return resolve();

        let done = false;
        const finish = () => {
            if (done) return;
            done = true;
            videoEl.removeEventListener('seeked', finish);
            clearTimeout(timer);
            resolve();
        };

        const timer = setTimeout(finish, timeoutMs);
        videoEl.addEventListener('seeked', finish, { once: true });
    });

export default function Score() {
    const { attemptId } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    const [scoreData, setScoreData] = useState(null);
    const [userVideoUrl, setUserVideoUrl] = useState(null);
    const [instructorVideoUrl, setInstructorVideoUrl] = useState(null);

    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [currentTime, setCurrentTime] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);

    const userVideoRef = useRef(null);
    const instructorVideoRef = useRef(null);

    useEffect(() => {
        let isMounted = true;
        let createdUserBlobUrl = null;
        let createdInstructorBlobUrl = null;

        const initializeData = async () => {
            try {
                const fetchedAttempt = attemptId ? await getPastDanceAttempt(attemptId) : null;
                const data = fetchedAttempt
                    ? { ...location.state?.scoreData, ...fetchedAttempt }
                    : location.state?.scoreData || null;

                let localVid = location.state?.localVideoUrl?.startsWith('blob:')
                    ? location.state.localVideoUrl
                    : null;

                if (!localVid && attemptId) {
                    createdUserBlobUrl = await getDanceAttemptStream(attemptId);
                    localVid = createdUserBlobUrl;
                }

                let refVid = location.state?.instructorVideoUrl?.startsWith('blob:')
                    ? location.state.instructorVideoUrl
                    : null;
                const refVideoId = extractRefVideoId(data);

                if (!refVid && refVideoId) {
                    createdInstructorBlobUrl = await getVideoStream(refVideoId);
                    refVid = createdInstructorBlobUrl;
                }

                if (isMounted) {
                    setScoreData(data);
                    setUserVideoUrl(localVid || null);
                    setInstructorVideoUrl(refVid || null);
                    setIsLoading(false);
                } else {
                    if (createdUserBlobUrl) URL.revokeObjectURL(createdUserBlobUrl);
                    if (createdInstructorBlobUrl) URL.revokeObjectURL(createdInstructorBlobUrl);
                }
            } catch (err) {
                console.error(err);
                if (createdUserBlobUrl) URL.revokeObjectURL(createdUserBlobUrl);
                if (createdInstructorBlobUrl) URL.revokeObjectURL(createdInstructorBlobUrl);
                if (isMounted) {
                    setError('Failed to load score data.');
                    setIsLoading(false);
                }
            }
        };

        initializeData();

        return () => {
            isMounted = false;
            if (createdUserBlobUrl) URL.revokeObjectURL(createdUserBlobUrl);
            if (createdInstructorBlobUrl) URL.revokeObjectURL(createdInstructorBlobUrl);
        };
    }, [attemptId, location.state]);

    const handleTimeUpdate = () => {
        if (userVideoRef.current && isPlaying) {
            setCurrentTime(userVideoRef.current.currentTime);
        }
    };

    const handleVideoEnded = () => {
        setIsPlaying(false);
    };

    const togglePlayPause = () => {
        if (!userVideoRef.current) return;

        if (isPlaying) {
            userVideoRef.current.pause();
            instructorVideoRef.current?.pause();
            setIsPlaying(false);
        } else {
            userVideoRef.current.play();
            instructorVideoRef.current?.play();
            setIsPlaying(true);
        }
    };

    const seekVideosToTime = async (newTime) => {
        if (!userVideoRef.current) return;

        const userVid = userVideoRef.current;
        const refVid = instructorVideoRef.current;

        // Recorded blobs can report non-finite durations, so fall back to the reference video duration
        const userDur = userVid.duration;
        const refDur = refVid?.duration || 0;
        const duration = Number.isFinite(userDur) && userDur > 0 ? userDur : refDur;
        const safeTime = duration > 0 ? Math.max(0, Math.min(newTime, duration)) : Math.max(0, newTime);

        const seekPromises = [];

        if (Math.abs(userVid.currentTime - safeTime) > 0.01) {
            seekPromises.push(waitForSeeked(userVid));
            userVid.currentTime = safeTime;
        }

        if (refVid && Math.abs(refVid.currentTime - safeTime) > 0.01) {
            seekPromises.push(waitForSeeked(refVid));
            refVid.currentTime = safeTime;
        }

        if (seekPromises.length > 0) {
            await Promise.all(seekPromises);
        }

        setCurrentTime(safeTime);
    };

    const skipSeconds = async (seconds) => {
        const anchorTime = Number.isFinite(userVideoRef.current?.currentTime)
            ? userVideoRef.current.currentTime
            : currentTime;
        await seekVideosToTime(anchorTime + seconds);
    };

    const skipToKeyframe = async (direction) => {
        const frames = getScoredFrames(scoreData);
        if (frames.length === 0 || !userVideoRef.current) return;

        // Pause both videos so frame comparison stays frozen at the target keyframe
        userVideoRef.current.pause();
        instructorVideoRef.current?.pause();
        setIsPlaying(false);

        const anchorTime = Number.isFinite(userVideoRef.current.currentTime)
            ? userVideoRef.current.currentTime
            : currentTime;

        let targetFrame = null;

        if (direction === 'next') {
            targetFrame = frames.find((f) => f.timestamp_sec > anchorTime + 0.05) || frames[frames.length - 1];
        } else if (direction === 'prev') {
            targetFrame = [...frames].reverse().find((f) => f.timestamp_sec < anchorTime - 0.05) || frames[0];
        }

        if (!targetFrame) return;
        await seekVideosToTime(targetFrame.timestamp_sec);
    };

    if (isLoading) {
        return (
            <div className="vh-100 bg-black d-flex justify-content-center align-items-center">
                <Spinner animation="border" variant="primary" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="vh-100 bg-black text-white d-flex flex-column justify-content-center align-items-center">
                <h3 className="mb-3">{error}</h3>
                <Button variant="outline-light" className="rounded-pill px-4" onClick={() => navigate('/')}>
                    Return to Menu
                </Button>
            </div>
        );
    }

    const attemptDate = scoreData?.created_at
        ? new Date(scoreData.created_at).toLocaleDateString()
        : new Date().toLocaleDateString();

    const totalScore = Math.round(scoreData?.score ?? scoreData?.total_score ?? 0);
    const scoreColor = totalScore >= 80 ? 'text-success' : totalScore >= 50 ? 'text-warning' : 'text-danger';

    const scoredFrames = getScoredFrames(scoreData);
    const activeFrame = scoredFrames.reduce((closest, frame) => {
        if (!closest) return frame;
        return Math.abs(frame.timestamp_sec - currentTime) < Math.abs(closest.timestamp_sec - currentTime)
            ? frame
            : closest;
    }, null);

    return (
        <div className="min-vh-100 bg-black text-light p-4 d-flex flex-column">
            <div className="container-fluid flex-grow-1 d-flex flex-column" style={{ maxWidth: '1400px' }}>
                <div className="d-flex justify-content-between align-items-center mb-4">
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        className="rounded-pill px-3 text-light"
                        onClick={() => navigate('/')}
                    >
                        &larr; Back to Menu
                    </Button>
                    <span className="text-secondary small">Attempt on {attemptDate}</span>
                </div>

                <div className="bg-dark border border-secondary rounded-4 p-4 mb-4 shadow d-flex flex-wrap justify-content-between align-items-center gap-3">
                    <div>
                        <div className="text-secondary text-uppercase small fw-semibold tracking-wide">
                            Overall Score
                        </div>
                        <div className="d-flex align-items-baseline gap-2">
                            <span className={`display-4 fw-bold ${scoreColor}`}>{totalScore}</span>
                            <span className="fs-4 text-secondary">/ 100</span>
                        </div>
                    </div>

                    {activeFrame && (
                        <div className="text-md-center">
                            <div className="text-secondary text-uppercase small fw-semibold mb-1">
                                Nearest Keyframe ({activeFrame.timestamp_sec.toFixed(2)}s)
                            </div>
                            <div className="d-flex align-items-center justify-content-center gap-2">
                                <Badge bg="info" text="dark" className="fs-6 px-3 py-2 rounded-pill">
                                    Score: {Math.round(activeFrame.score)}
                                </Badge>
                                <Badge bg="secondary" className="fs-6 px-3 py-2 rounded-pill">
                                    Delay: {activeFrame.delay_sec >= 0 ? `+${activeFrame.delay_sec.toFixed(2)}s` : `${activeFrame.delay_sec.toFixed(2)}s`}
                                </Badge>
                            </div>
                        </div>
                    )}

                    <div className="text-md-end">
                        <div className="text-secondary text-uppercase small fw-semibold mb-1">
                            vs. Last Attempt
                        </div>
                        <Badge bg="success" className="fs-6 px-3 py-2 rounded-pill">
                            &#9650; 28 pts
                        </Badge>
                    </div>
                </div>

                <div className="row g-4 flex-grow-1 mb-4">
                    <div className="col-lg-6 d-flex flex-column">
                        <div className="d-flex justify-content-between align-items-center mb-2 px-1">
                            <span className="fw-semibold text-light">Your Attempt</span>
                            <Badge bg="secondary" className="fw-normal">Camera</Badge>
                        </div>
                        <div
                            className="bg-dark border border-secondary rounded-4 flex-grow-1 position-relative overflow-hidden shadow-lg d-flex justify-content-center align-items-center"
                            style={{ minHeight: '360px' }}
                        >
                            {userVideoUrl ? (
                                <video
                                    ref={userVideoRef}
                                    src={userVideoUrl}
                                    className="position-absolute w-100 h-100 object-fit-contain"
                                    onTimeUpdate={handleTimeUpdate}
                                    onEnded={handleVideoEnded}
                                    playsInline
                                    muted
                                />
                            ) : (
                                <span className="text-secondary">User video unavailable</span>
                            )}
                        </div>
                    </div>

                    <div className="col-lg-6 d-flex flex-column">
                        <div className="d-flex justify-content-between align-items-center mb-2 px-1">
                            <span className="fw-semibold text-light">Instructor</span>
                            <Badge bg="primary" className="fw-normal">Reference</Badge>
                        </div>
                        <div
                            className="bg-dark border border-secondary rounded-4 flex-grow-1 position-relative overflow-hidden shadow-lg d-flex justify-content-center align-items-center"
                            style={{ minHeight: '360px' }}
                        >
                            {instructorVideoUrl ? (
                                <video
                                    ref={instructorVideoRef}
                                    src={instructorVideoUrl}
                                    className="position-absolute w-100 h-100 object-fit-contain"
                                    playsInline
                                />
                            ) : (
                                <span className="text-secondary">Instructor video unavailable</span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="d-flex justify-content-center pb-3">
                    <div className="bg-dark border border-secondary rounded-pill px-4 py-2 shadow-lg d-flex align-items-center gap-3">
                        <Button
                            variant="outline-light"
                            size="sm"
                            className="rounded-pill border-0 px-3 fs-5"
                            title="Back 1 second"
                            onClick={() => skipSeconds(-1)}
                        >
                            &laquo;
                        </Button>

                        <Button
                            variant="outline-light"
                            size="sm"
                            className="rounded-pill border-0 px-3 fs-5"
                            title="Previous keyframe"
                            onClick={() => skipToKeyframe('prev')}
                        >
                            &lsaquo;
                        </Button>

                        <Button
                            variant="primary"
                            size="sm"
                            className="rounded-pill px-3 fw-semibold"
                            onClick={togglePlayPause}
                        >
                            {isPlaying ? 'Pause' : 'Play'}
                        </Button>

                        <div
                            className="bg-warning text-dark rounded-pill px-3 py-1 fw-bold font-monospace fs-5"
                            style={{ minWidth: '88px', textAlign: 'center' }}
                        >
                            {currentTime.toFixed(2)}s
                        </div>

                        <Button
                            variant="outline-light"
                            size="sm"
                            className="rounded-pill border-0 px-3 fs-5"
                            title="Next keyframe"
                            onClick={() => skipToKeyframe('next')}
                        >
                            &rsaquo;
                        </Button>

                        <Button
                            variant="outline-light"
                            size="sm"
                            className="rounded-pill border-0 px-3 fs-5"
                            title="Forward 1 second"
                            onClick={() => skipSeconds(1)}
                        >
                            &raquo;
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
}