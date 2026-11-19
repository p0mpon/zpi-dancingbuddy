import VideoPreviewModal from "./VideoPreviewModal";
import {PREVIEW_MODALS_CONFIGS} from "../../../config/preview_config";
import {VideoProvider} from "../../../context/VideoContext";

export default function LibraryPreviewModal({previewVideo, onHide, switchToVideoView}) {
    const videoId = previewVideo?.id || previewVideo;
    return (
        <VideoProvider mode={'general'} videoId={videoId}>
            <VideoPreviewModal
                onHide={onHide}
                switchToVideoView={switchToVideoView}
                tabs={PREVIEW_MODALS_CONFIGS.general}/>
        </VideoProvider>
    )
}