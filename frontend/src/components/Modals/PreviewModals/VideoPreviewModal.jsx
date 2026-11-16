import React, {useState} from 'react';
import {Modal, Button, Row, Col, Tabs, Tab} from 'react-bootstrap';
import {PlayFill} from 'react-bootstrap-icons';
import {useVideo} from "../../../context/VideoContext";
import {formatDate} from "../../../utils/date_format";

export default function VideoPreviewModal({onHide, switchToVideoView, tabs}) {
    const [activeTab, setActiveTab] = useState(tabs[0].key);
    const {currentVideo, attempts} = useVideo();

    const lastAttempt = attempts.length > 0 ? attempts[0] : null;

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
            {currentVideo && (
                <Modal.Body className="p-0 h-100">
                    <Row className="g-0 h-100">
                        <Col md={8}
                             className="d-flex flex-column p-4 border-end border-secondary border-opacity-25 h-100">
                            <Tabs
                                id="preview-details"
                                activeKey={activeTab}
                                onSelect={(tab) => setActiveTab(tab)}
                                className="mb-3 flex-shrink-0"
                            >
                                {tabs.map(({eventKey, title, Component}) => (
                                    <Tab key={eventKey} eventKey={eventKey} title={title}>
                                        <Component />
                                    </Tab>
                                ))}
                            </Tabs>
                        </Col>

                        <Col md={4} className="d-flex flex-column bg-dark bg-opacity-25 p-4 h-100">
                            <p className="fw-bold text-light mb-1">{currentVideo.title}</p>
                            <p className="text-light fs-6 mb-3">
                                By <strong>{currentVideo.author_nickname}</strong>
                            </p>

                            <div className="ratio ratio-16x9 bg-dark mb-3 flex-shrink-0">
                                <video
                                    src={currentVideo.file}
                                    controls
                                    autoPlay
                                    muted
                                    poster={currentVideo.thumbnail_url}
                                    className="w-100 h-100 object-fit-contain"
                                />
                            </div>

                            <div>
                                <p>Likes: {currentVideo.likes_count}</p>
                            </div>

                            {lastAttempt && (
                                <div className="mb-3">
                                    <p className="fw-bold text-light mb-1">
                                        Your last
                                        attempt: {lastAttempt.status === 'done' ? lastAttempt.score : "Processing"} </p>
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
                                    <span>Practice!</span>
                                </Button>
                            </div>
                        </Col>
                    </Row>
                </Modal.Body>
            )}
        </Modal>
    );
}