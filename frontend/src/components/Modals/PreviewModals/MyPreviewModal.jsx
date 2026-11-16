import VideoPreviewModal from "./VideoPreviewModal";
import {Button, Form, Tab} from "react-bootstrap";
import {useState} from "react";
import {VideoProvider} from "../../../context/VideoContext";
import {PREVIEW_MODALS_CONFIGS} from "../../../config/preview_config";

export default function MyPreviewModal({previewVideo, onHide, switchToVideoView}) {
    const videoId = previewVideo?.id || previewVideo;
    return (
        <VideoProvider videoId={videoId}>
            <VideoPreviewModal
                onHide={onHide}
                switchToVideoView={switchToVideoView}
                tabs={PREVIEW_MODALS_CONFIGS.user_specific}/>
        </VideoProvider>
    )
}