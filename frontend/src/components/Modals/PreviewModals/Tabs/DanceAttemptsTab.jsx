import React from "react";
import {Spinner, Tab} from "react-bootstrap";
import useInfiniteScroll from "../../../../hooks/useInfiniteScroll";
import {formatDate} from "../../../../utils/date_format";
import {useVideo} from "../../../../context/VideoContext";

export default function DanceAttemptsTab() {
    const {
        attempts,
        loadingAttempts,
        hasMoreAttempts,
        fetchNextAttemptsPage
    } = useVideo();

    const { loaderRef, isLoadingMore } = useInfiniteScroll(fetchNextAttemptsPage, hasMoreAttempts);

    const lastAttempt = attempts.length > 0 ? attempts[0] : null;
    const previousAttempts = attempts.length > 1 ? attempts.slice(1) : [];
    
    return (
        <div className="overflow-y-auto pe-2" style={{maxHeight: '460px'}}>
            {loadingAttempts && attempts.length === 0 ? (
                <div className="text-center py-4">
                    <Spinner animation="border" variant="light" size="sm"/>
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
                                                <span
                                                    className={`fw-medium ${lastAttempt.score_diff_previous >= 0 ? 'text-success' : 'text-danger'}`}>
                                                                                {lastAttempt.score_diff_previous > 0 ? '+' : ''}{lastAttempt.score_diff_previous}
                                                                            </span>
                                            </div>
                                        )}
                                        {lastAttempt.score_diff_best !== null && (
                                            <div className="d-flex flex-column align-items-end">
                                                <span className="text-light opacity-75 small">vs Best</span>
                                                <span
                                                    className={`fw-medium ${lastAttempt.score_diff_best >= 0 ? 'text-success' : 'text-danger'}`}>
                                                                                {lastAttempt.score_diff_best > 0 ? '+' : ''}{lastAttempt.score_diff_best}
                                                                            </span>
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <span
                                        className="text-warning text-uppercase small fw-bold">{lastAttempt.status}</span>
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
                                                    <span
                                                        className={`small fw-medium ${attempt.score_diff_previous >= 0 ? 'text-success' : 'text-danger'}`}>
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
                                <Spinner animation="border" size="sm" variant="secondary"/>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}