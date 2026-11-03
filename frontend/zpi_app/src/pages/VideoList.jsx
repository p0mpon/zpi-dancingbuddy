import React, {useEffect, useState} from 'react';
import {Badge, Button, Row, Col, Card} from 'react-bootstrap';
import {Film} from 'react-bootstrap-icons';
import {useNavigate, useSearchParams} from "react-router-dom";
import {getAllVideos} from "../api/calls";
import VideoPreviewModal from "../components/Modals/VideoPreviewModal";


export default function VideoList() {
    const [searchParams, setSearchParams] = useSearchParams();
    const searchQuery = searchParams.get('search') || '';
    const [selectedVideo, setSelectedVideo] = useState(null);
    const navigate = useNavigate();

    const [videos, setVideos] = useState([]);
    useEffect(() => {
        getAllVideos()
            .then(r => {
                setVideos(Array.isArray(r) ? r : []);
            })
            .catch(err => {
                console.error("Failed to load videos:", err);
                setVideos([]);
            });
    }, [])

    useEffect(() => {
        const handleHashChange = () => {
            const hash = window.location.hash; // e.g., "#preview-1"
            if (hash.startsWith('#preview-')) {
                const videoId = parseInt(hash.replace('#preview-', ''), 10);
                const found = videos.find(v => v.id === videoId);
                setSelectedVideo(found || null);
            } else {
                setSelectedVideo(null);
            }
        };

        handleHashChange();

        window.addEventListener('hashchange', handleHashChange);
        return () => window.removeEventListener('hashchange', handleHashChange);
    }, [videos]);

    const filteredVideos = videos.filter(video => {
        return video?.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            video?.author.toLowerCase().includes(searchQuery.toLowerCase());
    });

    const resetSearch = () => {
        setSearchParams({});
    };
    
    const showPreview = (video) => {
        window.location.hash = `#preview-${video.id}`;
    }

    const closePreview = () => {
        window.history.pushState(null, '', window.location.pathname);
        setSelectedVideo(null);
    };
    
    const switchToVideo = () => {
        console.log('hey it works');
        navigate('/video/' + selectedVideo.id, {
            state: {
                currentVideo: selectedVideo
            }
        });
        setSelectedVideo(null);
    }

    return (
        <>
            <div className="d-flex align-items-center justify-content-between mb-4">
                <h4 className="fw-bold mb-0 d-flex align-items-center gap-2">
                    <Badge bg="secondary" className="fw-normal fs-7">
                        {filteredVideos.length} {filteredVideos.length === 1 ? 'video' : 'videos'}
                    </Badge>
                </h4>
            </div>

            {filteredVideos.length === 0 ? (
                <div className="text-center py-5 bg-black rounded-4 border border-secondary p-4">
                    <div className="text-muted mb-3">
                        <Film size={48}/>
                    </div>
                    <h5 className="text-light mb-1">No videos found</h5>
                    {searchQuery && (
                        <Button
                            variant="outline-light"
                            size="sm"
                            className="mt-2"
                            onClick={resetSearch}
                        >
                            Reset search
                        </Button>
                    )}
                </div>
            ) : (
                <Row xs={1} md={2} lg={3} className="g-4">
                    {filteredVideos.map((video) => (
                        <Col key={video.id}>
                            <Card
                                bg="black"
                                text="light"
                                className="h-100 border-secondary shadow-sm"
                                onClick={() => showPreview(video)}
                                style={{cursor: 'pointer', transition: 'transform 0.2s ease, border-color 0.2s ease'}}
                            >
                                <Card.Body className="d-flex flex-column justify-content-between p-3">
                                    <div>
                                        <Card.Title className="fs-6 fw-bold text-light line-clamp-2 mb-2">
                                            {video.title}
                                        </Card.Title>
                                    </div>

                                    <div
                                        className="pt-3 border-top border-secondary d-flex align-items-center justify-content-between text-muted fs-8">
                                        <div className="d-flex align-items-center gap-2">
                                            {/*<Image src={video.authorAvatar} alt={video.author} roundedCircle width={20} height={20} /> */}
                                            <span className="text-light fw-medium">{video.author}</span>
                                        </div>
                                    </div>
                                </Card.Body>
                            </Card>
                        </Col>
                    ))}
                </Row>
            )}
            {selectedVideo && (
                <VideoPreviewModal
                    previewVideo={selectedVideo}
                    onHide = {closePreview}
                    switchToVideoView = {switchToVideo}
                />
            )}
        </>
    )
}