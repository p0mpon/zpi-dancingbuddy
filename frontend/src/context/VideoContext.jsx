import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getFullVideo, getDanceAttemptsForVideo } from "../api/calls";

const VideoContext = createContext(null);

export const VideoProvider = ({ videoId, children }) => {
    const [currentVideo, setCurrentVideo] = useState(null);

    const [attempts, setAttempts] = useState([]);
    const [nextAttemptsUrl, setNextAttemptsUrl] = useState(null);
    const [loadingAttempts, setLoadingAttempts] = useState(true);

    useEffect(() => {
        if (!videoId) return;
        let isMounted = true;

        getFullVideo(videoId)
            .then(video => { if (isMounted) setCurrentVideo(video); })
            .catch(err => console.error("Failed to fetch video:", err));

        return () => { isMounted = false; };
    }, [videoId]);

    useEffect(() => {
        if (!videoId) return;
        let isMounted = true;
        setLoadingAttempts(true);

        getDanceAttemptsForVideo(videoId)
            .then(data => {
                if (isMounted) {
                    setAttempts(data.results || []);
                    setNextAttemptsUrl(data.next);
                }
            })
            .catch(() => { if (isMounted) setAttempts([]); })
            .finally(() => { if (isMounted) setLoadingAttempts(false); });

        return () => { isMounted = false; };
    }, [videoId]);

    const refreshVideo = useCallback(async (videoId) => {
        const idToFetch = videoId ?? currentVideo?.id;
        if (!idToFetch) return null;

        try {
            const video = await getFullVideo(idToFetch);
            setCurrentVideo(video);
            return video;
        } catch (err) {
            console.error("Failed to fetch video:", err);
        }
    }, [currentVideo?.id]);

    const fetchNextAttemptsPage = useCallback(() => {
        if (!nextAttemptsUrl || !videoId) return Promise.resolve();

        return getDanceAttemptsForVideo(videoId, nextAttemptsUrl)
            .then(data => {
                setAttempts(prev => [...prev, ...(data.results || [])]);
                setNextAttemptsUrl(data.next);
            })
            .catch(console.error);
    }, [videoId, nextAttemptsUrl]);

    return (
        <VideoContext.Provider value={{
            currentVideo,
            setCurrentVideo,
            attempts,
            loadingAttempts,
            hasMoreAttempts: !!nextAttemptsUrl,
            fetchNextAttemptsPage,
            refreshVideo,
        }}>
            {children}
        </VideoContext.Provider>
    );
};

export const useVideo = () => useContext(VideoContext);