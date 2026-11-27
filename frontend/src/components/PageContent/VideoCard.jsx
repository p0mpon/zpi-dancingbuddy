import {Badge, Button, Card} from "react-bootstrap";
import React, {useState} from "react";
import {Film, Heart, HeartFill} from "react-bootstrap-icons";
import UserAvatar from "./UserAvatar";
import {LikeVideo, UnlikeVideo} from "../../api/calls";

export default function VideoCard({mode, video, showPreview, onVideoUpdated}) {
    const [isLiking, setIsLiking] = useState(false);
    if (!video) return null;
    const isLiked = Boolean(video.liked_by_me);

    const handleLikeClick = async (e) => {
        e.stopPropagation();
        if (isLiking) return;

        setIsLiking(true);
        try {
            const nextLiked = !isLiked;
            const response = nextLiked
                ? await LikeVideo(video.id)
                : await UnlikeVideo(video.id);

            const currentCount = typeof video.likes_count === "number" ? video.likes_count : 0;
            const nextCount =
                typeof response?.likes_count === "number"
                    ? response.likes_count
                    : Math.max(0, currentCount + (nextLiked ? 1 : -1));

            const updatedVideo = {
                ...video,
                ...(typeof response === "object" && response !== null ? response : {}),
                liked_by_me:
                    typeof response?.liked_by_me === "boolean"
                        ? response.liked_by_me
                        : nextLiked,
                likes_count: nextCount,
            };

            onVideoUpdated?.(updatedVideo);
        } catch (err) {
            console.error("Failed to toggle like:", err);
        } finally {
            setIsLiking(false);
        }
    };

    return (
        <Card
            bg="black"
            text="light"
            className="h-100 border-secondary shadow-sm overflow-hidden"
            onClick={() => showPreview(video)}
            style={{
                cursor: 'pointer',
                transition: 'transform 0.2s ease, border-color 0.2s ease'
            }}
        >
            {video.thumbnail_url ? (
                <div className="ratio ratio-16x9 bg-dark">
                    <Card.Img
                        src={video.thumbnail_url}
                        alt={video.title}
                        className="object-fit-cover"
                    />
                </div>
            ) : (
                <div className="ratio ratio-16x9 bg-dark d-flex align-items-center justify-content-center">
                    <Film size={48} className="text-secondary"/>
                </div>
            )}

            <Card.Body className="d-flex flex-column justify-content-between p-3">
                <div>
                    <div className="d-flex align-items-center gap-2 mb-1">
                        <Card.Title className="fs-4 fw-bold text-light line-clamp-2 mb-0">
                            {video.title}
                        </Card.Title>

                        {video.visibility === 'private' && (
                            <Badge
                                bg="transparent"
                                text="light"
                                className="border border-secondary rounded-pill fw-normal"
                            >
                                Private
                            </Badge>
                        )}
                    </div>

                    {(video.song_title || video.song_author) && (
                        <p className="text-secondary fs-5 mb-2">
                            🎵 {video.song_title || "Unknown Song"}
                            {video.song_author ? ` by ${video.song_author}` : ""}
                        </p>
                    )}
                </div>


                <div
                    className="pt-3 border-top border-secondary d-flex align-items-center justify-content-between text-muted fs-6 mt-2">
                    <div className="d-flex align-items-center gap-2">
                        {mode === 'general' ? (
                            <>
                                <UserAvatar avatarUrl={video.author_avatar_url} size={'24px'}/>
                                <span><strong
                                    className="text-white">{video.author_nickname}</strong></span>
                            </>
                        ) : (
                            <span className="text-light">Analysis status: <strong
                                className="text-white">{video.analysis_status}</strong></span>
                        )}
                    </div>
                    {mode === 'general' && (
                        <Button
                            type="button"
                            variant="link"
                            onClick={handleLikeClick}
                            disabled={isLiking}
                            aria-label={isLiked ? "Unlike video" : "Like video"}
                            className="p-0 text-decoration-none d-inline-flex align-items-center gap-1 text-light"
                        >
                            {isLiked ? (
                                <HeartFill size={18} className="text-danger"/>
                            ) : (
                                <Heart size={18} className="text-secondary"/>
                            )}
                            {typeof video.likes_count === "number" && (
                                <span className="text-secondary small">{video.likes_count}</span>
                            )}
                        </Button>
                    )}
                </div>
            </Card.Body>
        </Card>
    )
}