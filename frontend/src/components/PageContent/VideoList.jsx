import React, {useCallback, useEffect, useState} from 'react';
import {Button, Row, Col, Spinner} from 'react-bootstrap';
import {Film} from 'react-bootstrap-icons';
import {useNavigate} from "react-router-dom";
import useInfiniteScroll from "../../hooks/useInfiniteScroll";
import VideoCard from "../../components/PageContent/VideoCard";
import {VIDEO_LIST_CONFIGS} from "../../config/video_list_config";
import useVideoListParams from "../../hooks/useVideoListParams";


export default function VideoList({mode}) {
    const config = VIDEO_LIST_CONFIGS[mode] || VIDEO_LIST_CONFIGS.general;
    const { fetchFunction, VideoModal } = config;

    const { query, sort, getFilters, setQuery } = useVideoListParams();

    const difficultyValues = getFilters("difficulty");
    const statusValues = getFilters("analysis_status");
    const visibilityValues = getFilters("visibility");

    const difficultyKey = difficultyValues.join(",");
    const statusKey = statusValues.join(",");
    const visibilityKey = visibilityValues.join(",");

    const navigate = useNavigate();

    const [videos, setVideos] = useState([]);
    const [totalCount, setTotalCount] = useState(0);
    const [selectedVideo, setSelectedVideo] = useState(null);
    const [nextUrl, setNextUrl] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    const buildRequestParams = useCallback(
        (pageNextUrl = null) => ({
            searchQuery: query,
            ordering: sort,
            difficulty: difficultyKey,
            analysisStatus: statusKey,
            visibility: visibilityKey,
            nextUrl: pageNextUrl,
        }),
        [query, sort, difficultyKey, statusKey, visibilityKey]
    );

    useEffect(() => {
        let cancelled = false;
        setIsLoading(true);
        setVideos([]);
        setNextUrl(null);

        fetchFunction(buildRequestParams(null))
            .then((data) => {
                if (cancelled) return;
                setVideos(data.results || []);
                setNextUrl(data.next || null);
                setTotalCount(data.count ?? 0);
            })
            .catch((err) => {
                if (!cancelled) console.error("Failed to load videos:", err);
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [fetchFunction, buildRequestParams]);

    const fetchNextPage = useCallback(() => {
        if (!nextUrl) return Promise.resolve();

        return fetchFunction(buildRequestParams(nextUrl))
            .then((data) => {
                const newVideos = data.results || [];
                setVideos((prev) => {
                    const existingIds = new Set(prev.map((v) => v.id));
                    const uniqueNewVideos = newVideos.filter((v) => !existingIds.has(v.id));
                    return [...prev, ...uniqueNewVideos];
                });
                setNextUrl(data.next || null);
            })
            .catch(console.error);
    }, [nextUrl, fetchFunction, buildRequestParams]);

    const { loaderRef, isLoadingMore } = useInfiniteScroll(fetchNextPage, !!nextUrl);

    useEffect(() => {
        const handleHashChange = () => {
            const hash = window.location.hash;
            if (hash.startsWith("#preview-")) {
                const videoId = parseInt(hash.replace("#preview-", ""), 10);
                setSelectedVideo((prev) => {
                    if (prev && prev.id === videoId) return prev;
                    return videos.find((v) => v.id === videoId) || null;
                });
            } else {
                setSelectedVideo(null);
            }
        };

        handleHashChange();
        window.addEventListener("hashchange", handleHashChange);
        return () => window.removeEventListener("hashchange", handleHashChange);
    }, [videos]);

    const resetSearch = () => setQuery("");

    const showPreview = (video) => {
        window.location.hash = `preview-${video.id}`;
    };

    const closePreview = () => {
        window.history.pushState(null, "", window.location.pathname + window.location.search);
        setSelectedVideo(null);
    };

    const handleVideoUpdated = useCallback((updatedVideo) => {
        setVideos((prev) =>
            prev.map((v) => (v.id === updatedVideo.id ? { ...v, ...updatedVideo } : v))
        );
        setSelectedVideo((prev) =>
            prev && prev.id === updatedVideo.id ? { ...prev, ...updatedVideo } : prev
        );
    }, []);

    const handleVideoDeleted = useCallback((videoId) => {
        setVideos((prev) => prev.filter((v) => v.id !== videoId));
        setTotalCount((prev) => Math.max(0, prev - 1));
        setSelectedVideo((prev) => (prev && prev.id === videoId ? null : prev));
        if (window.location.hash === `#preview-${videoId}`) {
            window.history.replaceState(null, "", window.location.pathname + window.location.search);
        }
    }, []);
    
    const switchToVideo = () => {
        if (!selectedVideo) return;
        navigate("/video/" + selectedVideo.id, {
            state: {
                currentVideo: selectedVideo,
                mode,
            },
        });
        setSelectedVideo(null);
    };

    return (
        <>
            {isLoading && videos.length === 0 ? (
                <div className="text-center py-5">
                    <Spinner animation="border" variant="light"/>
                </div>
            ) : videos.length === 0 ? (
                <div className="text-center py-5 bg-black rounded-4 border border-secondary p-4">
                    <div className="text-muted mb-3"><Film size={48}/></div>
                    <h5 className="text-light mb-1">No videos found</h5>
                    {query && (
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
                                <VideoCard key={video.id} mode={mode} video={video} showPreview={showPreview} onVideoUpdated={handleVideoUpdated} />
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
                    onVideoUpdated={handleVideoUpdated}
                    onVideoDelete={handleVideoDeleted}
                />
            )}
        </>
    )
}