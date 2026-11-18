import {Card} from "react-bootstrap";
import React from "react";
import {Film} from "react-bootstrap-icons";

export default function VideoCard(video, showPreview) {
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
                    <Film size={48} className="text-secondary" />
                </div>
            )}

            <Card.Body className="d-flex flex-column justify-content-between p-3">
                <div>
                    <Card.Title className="fs-4 fw-bold text-light line-clamp-2 mb-1">
                        {video.title}
                    </Card.Title>

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
                                                <span className="text-light">Uploaded by <strong
                                                    className="text-white">{video.author}</strong></span>
                    </div>
                </div>
            </Card.Body>
        </Card>
    )
}