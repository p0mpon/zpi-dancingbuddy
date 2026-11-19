import React, {useCallback, useEffect, useState} from 'react';
import {Badge, Button, Row, Col, Spinner} from 'react-bootstrap';
import {Film} from 'react-bootstrap-icons';
import {useNavigate, useSearchParams} from "react-router-dom";
import useInfiniteScroll from "../hooks/useInfiniteScroll";
import VideoCard from "../components/PageContent/VideoCard";
import {VIDEO_LIST_CONFIGS} from "../config/video_list_config";


export default function VideoList({mode}) {
    const config = VIDEO_LIST_CONFIGS[mode] || VIDEO_LIST_CONFIGS.general;
    const {title, fetchFunction, VideoModal, filters} = config;

    const [searchParams, setSearchParams] = useSearchParams();
    const searchQuery = searchParams.get('search') || '';
    const difficultyQuery = searchParams.get('difficulty') || '';
    const statusQuery = searchParams.get('analysis_status') || '';
    const visibilityQuery = searchParams.get('visibility') || '';
    const navigate = useNavigate();

    const [videos, setVideos] = useState([]);
    const [totalCount, setTotalCount] = useState(0);
    const [selectedVideo, setSelectedVideo] = useState(null);

    const [nextUrl, setNextUrl] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        setIsLoading(true);
        setVideos([]);
        setNextUrl(null);

        const params = {
            search: searchParams.get('search') || '',
            difficulty: searchParams.get('difficulty') || '',
            analysisStatus: searchParams.get('analysis_status') || '',
            visibility: searchParams.get('visibility') || '',
            nextUrl: null,
        };

        fetchFunction(params)
            .then(data => {
                setVideos(data.results || []);
                setNextUrl(data.next);
                setTotalCount(data.count);
            })
            .catch(err => console.error("Failed to load videos:", err))
            .finally(() => setIsLoading(false));
    }, [searchQuery, difficultyQuery, statusQuery, visibilityQuery, fetchFunction]);

    const fetchNextPage = useCallback(() => {
        if (!nextUrl) return Promise.resolve();

        const params = {
            search: searchParams.get('search') || '',
            difficulty: searchParams.get('difficulty') || '',
            analysisStatus: searchParams.get('analysis_status') || '',
            visibility: searchParams.get('visibility') || '',
            nextUrl: nextUrl,
        };

        return fetchFunction(params)
            .then(data => {
                const newVideos = data.results || [];
                setVideos(prev => {
                    const existingIds = new Set(prev.map(v => v.id));
                    const uniqueNewVideos = newVideos.filter(v => !existingIds.has(v.id));
                    return [...prev, ...uniqueNewVideos];
                });
                setNextUrl(data.next);
            })
            .catch(console.error);
    }, [nextUrl, searchQuery, difficultyQuery, statusQuery, visibilityQuery]);

    const {loaderRef, isLoadingMore} = useInfiniteScroll(fetchNextPage, !!nextUrl);

    useEffect(() => {
        const handleHashChange = () => {
            const hash = window.location.hash;
            if (hash.startsWith('#preview-')) {
                const videoId = parseInt(hash.replace('#preview-', ''), 10);
                setSelectedVideo(prev => {
                    if (prev && prev.id === videoId) return prev;
                    return videos.find(v => v.id === videoId) || null;
                });
            } else {
                setSelectedVideo(null);
            }
        };

        handleHashChange();

        window.addEventListener('hashchange', handleHashChange);
        return () => window.removeEventListener('hashchange', handleHashChange);
    }, [videos]);

    const resetSearch = () => setSearchParams({});

    const showPreview = (video) => {
        window.location.hash = `preview-${video.id}`;
    };

    const closePreview = () => {
        window.history.pushState(null, '', window.location.pathname + window.location.search);
        setSelectedVideo(null);
    };

    const switchToVideo = () => {
        navigate('/video/' + selectedVideo.id, {
            state: {
                currentVideo: selectedVideo,
                mode: mode
            },
        });
        setSelectedVideo(null);
    };

    return (
        <>
            <div className="d-flex align-items-center justify-content-between mb-4">
                <h4 className="fw-bold mb-0 d-flex align-items-center gap-2">
                    <Badge bg="secondary" className="fw-normal fs-5">
                        {totalCount} {totalCount === 1 ? 'video' : 'videos'}
                    </Badge>
                </h4>
            </div>

            {isLoading && videos.length === 0 ? (
                <div className="text-center py-5">
                    <Spinner animation="border" variant="light"/>
                </div>
            ) : videos.length === 0 ? (
                <div className="text-center py-5 bg-black rounded-4 border border-secondary p-4">
                    <div className="text-muted mb-3"><Film size={48}/></div>
                    <h5 className="text-light mb-1">No videos found</h5>
                    {searchQuery && (
                        <Button variant="outline-light" size="sm" className="mt-2" onClick={resetSearch}>
                            Reset search
                        </Button>
                    )}
                </div>
            ) : (
                <>
                    <Row xs={1} md={2} lg={3} className="g-4">
                        {videos.map((video) => (
                            <Col>
                                <VideoCard key={video.id} mode={mode} video={video} showPreview={showPreview}/>
                            </Col>
                        ))}
                    </Row>
                    <div ref={loaderRef} className="text-center py-4">
                        {isLoadingMore && (
                            <div className="d-flex justify-content-center align-items-center gap-2 text-muted">
                                <Spinner animation="border" size="sm"/>
                                <span>Loading more videos...</span>
                            </div>
                        )}
                    </div>
                </>
            )}
            {selectedVideo && (
                <VideoModal
                    previewVideo={selectedVideo}
                    onHide={closePreview}
                    switchToVideoView={switchToVideo}
                />
            )}
        </>
    )
}