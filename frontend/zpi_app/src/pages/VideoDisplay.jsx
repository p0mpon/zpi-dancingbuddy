import React from 'react';
import {Button, Row, Col} from 'react-bootstrap';
import {useLocation, useNavigate} from "react-router-dom";

export default function VideoDisplay() {
    const navigate = useNavigate();
    const location = useLocation();

    const currentVideo = location.state?.currentVideo;

    if (!currentVideo) {
        return <div className="p-6 text-red-500">Video not found!</div>;
    }

    const backToVideoList = () => {
        navigate('/');
    }
    return (
        <Row className="g-4">
            <Col lg={8}>
                <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={backToVideoList}
                    className="mb-3 d-flex align-items-center gap-2 text-light border-secondary"
                >
                    <span>← Back</span>
                </Button>

                <div
                    className="ratio ratio-16x9 bg-black rounded-4 overflow-hidden border border-secondary shadow-lg mb-4">
                    <video
                        src={currentVideo.url}
                        controls
                        autoPlay
                        poster={currentVideo.thumbnail}
                        className="w-100 h-100 object-fit-contain"
                    >
                        Your browser does not support the video tag.
                    </video>
                </div>

                <div>
                    <h3 className="fw-bold text-light mb-3">{currentVideo.title}</h3>

                    <div
                        className="d-flex flex-wrap align-items-center justify-content-between gap-3 pb-4 border-bottom border-secondary">
                        <div className="d-flex align-items-center gap-3">
                            {/*<Image src={currentVideo.authorAvatar} alt={currentVideo.author} roundedCircle width={45} height={45} className="border border-secondary" />*/}
                            <div>
                                <h6 className="fw-bold mb-0 text-light">{currentVideo.author}</h6>
                                <p> tu jest nic tak zwane</p>
                            </div>
                        </div>
                    </div>

                </div>
            </Col>
        </Row>
    )
}