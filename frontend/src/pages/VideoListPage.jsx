import FilterSelector from "..//components/filters/FilterSelector";
import { VIDEO_LIST_CONFIGS } from "../config/video_list_config";
import {getFilterGroupsForMode, SORTING_OPTIONS} from "../config/filters";
import SortingSelector from "../components/filters/SortingSelector";
import VideoList from "../components/PageContent/VideoList";

export default function VideoListPage({ mode = "general" }) {
    const config = VIDEO_LIST_CONFIGS[mode] || VIDEO_LIST_CONFIGS.general;
    const filters = getFilterGroupsForMode(config);

    return (
        <>
            <div className="d-flex flex-column gap-3 mb-4">
                <h2 className="h4 mb-0">{config.title}</h2>

                <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">
                    {filters.length > 0 && (
                        <FilterSelector filterGroups={filters} />
                    )}

                    <SortingSelector />
                </div>
            </div>

            <VideoList mode={mode} />
        </>
    );
}