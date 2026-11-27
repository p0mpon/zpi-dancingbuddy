import {useCallback, useRef, useState} from 'react';

export default function useInfiniteScroll(loadMoreAction, hasMore) {
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const observer = useRef(null);

    const loaderRef = useCallback((node) => {
        if (isLoadingMore) return;
        if (observer.current) observer.current.disconnect();

        observer.current = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && hasMore) {
                setIsLoadingMore(true);

                Promise.resolve(loadMoreAction())
                    .catch(() => {})
                    .finally(() => {
                    setIsLoadingMore(false);
                });
            }
        }, {
            threshold: 0.1,
            rootMargin: '200px'
        });

        if (node) {
            observer.current.observe(node);
        }
    }, [isLoadingMore, hasMore, loadMoreAction]);

    return {loaderRef, isLoadingMore};
}