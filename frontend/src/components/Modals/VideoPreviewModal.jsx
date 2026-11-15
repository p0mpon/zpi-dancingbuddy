import React, { useEffect, useState, useCallback } from 'react';
import { Modal, Button, Row, Col, Tabs, Tab, Spinner } from 'react-bootstrap';
import { PlayFill } from 'react-bootstrap-icons';
import { getDanceAttemptsForVideo } from "../../api/calls";
import useInfiniteScroll from "../../hooks/infinite_scroll";

export default function VideoPreviewModal({ previewVideo, onHide, switchToVideoView }) {
    const [activeTab, setActiveTab] = useState('video-details');
    const [attempts, setAttempts] = useState([]);
    const [nextUrl, setNextUrl] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    const lastAttempt = attempts.length > 0 ? attempts[0] : null;
    const previousAttempts = attempts.length > 1 ? attempts.slice(1) : [];

    const fetchNextPage = useCallback(() => {
        if (!nextUrl) return Promise.resolve();

        return getDanceAttemptsForVideo(previewVideo.id, nextUrl)
            .then(data => {
                setAttempts(prev => [...prev, ...(data.results || [])]);
                setNextUrl(data.next);
            })
            .catch(console.error);
    }, [previewVideo?.id, nextUrl]);

    const { loaderRef, isLoadingMore } = useInfiniteScroll(fetchNextPage, !!nextUrl);

    useEffect(() => {
        if (!previewVideo?.id) return;
        setIsLoading(true);
        getDanceAttemptsForVideo(previewVideo.id)
            .then((data) => {
                setAttempts(data.results || []);
                setNextUrl(data.next);
            })
            .catch(() => setAttempts([]))
            .finally(() => setIsLoading(false));
    }, [previewVideo?.id]);

    const formatDate = (dateString) => {
        if (!dateString) return "Unknown Date";
        return new Date(dateString).toLocaleDateString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    };

    return (
        <Modal
            show={true}
            onHide={onHide}
            centered
            size="lg"
            dialogClassName="preview-modal-box"
            contentClassName="bg-black text-light border border-secondary rounded-4 shadow-lg overflow-hidden"
        >
            <Modal.Header closeButton></Modal.Header>
            {previewVideo && (
                <Modal.Body className="p-0 h-100">
                    <Row className="g-0 h-100">
                        <Col md={8} className="d-flex flex-column p-4 border-end border-secondary border-opacity-25 h-100">
                            <Tabs
                                id="preview-details"
                                activeKey={activeTab}
                                onSelect={(tab) => setActiveTab(tab)}
                                className="mb-3 flex-shrink-0"
                            >
                                <Tab eventKey="video-details" title="Details">
                                    <div className="overflow-y-auto pe-2" style={{maxHeight: '460px'}}>
                                        <p className="text-light mb-1">Song title: {previewVideo.song_title}</p>
                                        <p className="text-light fs-6 mb-4">
                                            Artist: {previewVideo.song_author}
                                            {previewVideo.id}
                                        </p>

                                        <div className="mb-3">
                                            <span className="text-secondary fw-semibold">Difficulty: </span>
                                            <span className="text-light">{previewVideo.difficulty}</span>
                                        </div>

                                        <hr className="border-secondary opacity-25 my-3"/>

                                        <div>
                                            <h6 className="text-secondary text-uppercase fs-6 fw-semibold mb-2">Description</h6>
                                            <p className="text-light opacity-75">
                                                {previewVideo.description || "No description provided."}
                                            </p>
                                        </div>
                                    </div>
                                </Tab>

                                <Tab eventKey="attempt-details" title="Dance attempts">
                                    <div className="overflow-y-auto pe-2" style={{ maxHeight: '460px' }}>
                                        {isLoading && attempts.length === 0 ? (
                                            <div className="text-center py-4">
                                                <Spinner animation="border" variant="light" size="sm" />
                                            </div>
                                        ) : attempts.length === 0 ? (
                                            <div className="py-3">
                                                <p className="text-light fs-6 mb-1">No attempts yet</p>
                                                <p className="text-secondary">Play the video, you coward.</p>
                                            </div>
                                        ) : (
                                            <div className="d-flex flex-column gap-4">
                                                {lastAttempt && (
                                                    <div className="bg-dark bg-opacity-50 rounded-4 border border-secondary p-3 shadow-sm">
                                                        <h6 className="text-secondary text-uppercase fs-6 fw-semibold mb-3">Latest Attempt</h6>

                                                        <div className="d-flex justify-content-between align-items-center mb-2 gap-3">
                                                            <span className="text-light fw-medium">{formatDate(lastAttempt.created_at)}</span>

                                                            {lastAttempt.status === 'done' ? (
                                                                <>
                                                                    <span className="fw-bold fs-5">{lastAttempt.score}</span>
                                                                    {lastAttempt.score_diff_previous !== null && (
                                                                        <div className="d-flex flex-column align-items-end">
                                                                            <span className="text-light opacity-75 small">vs Prev</span>
                                                                            <span className={`fw-medium ${lastAttempt.score_diff_previous >= 0 ? 'text-success' : 'text-danger'}`}>
                                                                                {lastAttempt.score_diff_previous > 0 ? '+' : ''}{lastAttempt.score_diff_previous}
                                                                            </span>
                                                                        </div>
                                                                    )}
                                                                    {lastAttempt.score_diff_best !== null && (
                                                                        <div className="d-flex flex-column align-items-end">
                                                                            <span className="text-light opacity-75 small">vs Best</span>
                                                                            <span className={`fw-medium ${lastAttempt.score_diff_best >= 0 ? 'text-success' : 'text-danger'}`}>
                                                                                {lastAttempt.score_diff_best > 0 ? '+' : ''}{lastAttempt.score_diff_best}
                                                                            </span>
                                                                        </div>
                                                                    )}
                                                                </>
                                                            ) : (
                                                                <span className="text-warning text-uppercase small fw-bold">{lastAttempt.status}</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                )}

                                                {previousAttempts.length > 0 && (
                                                    <div>
                                                        <h6 className="text-secondary text-uppercase fs-6 fw-semibold mb-3">Previous History</h6>
                                                        <div className="d-flex flex-column gap-2">
                                                            {previousAttempts.map((attempt) => (
                                                                <div
                                                                    key={attempt.id}
                                                                    className="bg-black rounded-3 p-2 px-3 border border-secondary border-opacity-25 d-flex justify-content-between align-items-center"
                                                                >
                                                                    <span className="text-light fs-6">{formatDate(attempt.created_at)}</span>

                                                                    {attempt.status === 'done' ? (
                                                                        <div className="d-flex gap-3 align-items-center">
                                                                            <span className="fw-bold">{attempt.score}</span>
                                                                            {attempt.score_diff_previous !== null && (
                                                                                <span className={`small fw-medium ${attempt.score_diff_previous >= 0 ? 'text-success' : 'text-danger'}`}>
                                                                                    {attempt.score_diff_previous > 0 ? '+' : ''}{attempt.score_diff_previous}
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                    ) : (
                                                                        <span className="text-warning small text-uppercase">{attempt.status}</span>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                                <div ref={loaderRef} className="text-center py-2">
                                                    {isLoadingMore && (
                                                        <div className="d-flex justify-content-center align-items-center gap-2 text-muted">
                                                            <Spinner animation="border" size="sm" variant="secondary" />
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </Tab>
                            </Tabs>
                        </Col>

                        <Col md={4} className="d-flex flex-column bg-dark bg-opacity-25 p-4 h-100">
                            <p className="fw-bold text-light mb-1">{previewVideo.title}</p>
                            <p className="text-light fs-6 mb-3">
                                By {previewVideo.author}
                            </p>

                            <div className="ratio ratio-16x9 bg-dark mb-3 flex-shrink-0">
                                <video
                                    src={previewVideo.file}
                                    controls
                                    autoPlay
                                    muted
                                    poster={previewVideo.thumbnail_url}
                                    className="w-100 h-100 object-fit-contain"
                                />
                            </div>

                            <div>
                                <p>Likes: {previewVideo.likes_count}</p>
                            </div>

                            {lastAttempt && (
                            <div className="mb-3">
                                <p className="fw-bold text-light mb-1">
                                    Your last attempt: {lastAttempt.status === 'done' ? lastAttempt.score : "Processing"} </p>
                                <p className="text-light fs-6">
                                    On {lastAttempt ? formatDate(lastAttempt.created_at) : "N/A"}
                                </p>
                            </div>
                            )}

                            <div className="mt-auto d-flex flex-column gap-2">
                                <Button
                                    variant="primary"
                                    size="sm"
                                    className="w-100 d-flex align-items-center justify-content-center gap-2"
                                    onClick={switchToVideoView}
                                >
                                    <PlayFill size={15}/>
                                    <span>Play!</span>
                                </Button>
                            </div>
                        </Col>
                    </Row>
                </Modal.Body>
            )}
        </Modal>
    );
}