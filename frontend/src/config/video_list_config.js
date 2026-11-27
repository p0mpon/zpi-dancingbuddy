import {getAllVideos, getMyVideos} from "../api/calls";
import LibraryPreviewModal from "../components/Modals/PreviewModals/LibraryPreviewModal";
import MyPreviewModal from "../components/Modals/PreviewModals/MyPreviewModal";

export const VIDEO_LIST_CONFIGS = {
    general: {
        title: "Browse Videos",
        fetchFunction: getAllVideos,
        VideoModal: LibraryPreviewModal,
        filters: ['difficulty'],
    },
    user_specific: {
        title: "My Videos",
        fetchFunction: getMyVideos,
        VideoModal: MyPreviewModal,
        filters: ['difficulty', 'analysis_status', 'visibility'],
    }
};