import {SORTING_OPTIONS} from "../../config/filters";
import useVideoQueryParams from "../../hooks/useVideoListParams";

export default function SortingSelector({}){
    const { sort, setSort } = useVideoQueryParams();
    
    return (
        <div
            role="radiogroup"
            aria-label="Sort videos"
            className="d-flex flex-wrap align-items-center gap-2 ms-auto"
        >
            {SORTING_OPTIONS.map((opt) => {
                const isSelected = sort === opt.key;
                return (
                    <button
                        key={opt.key}
                        type="button"
                        role="radio"
                        aria-checked={isSelected}
                        onClick={() => setSort(opt.key)}
                        className={`btn btn-sm rounded-pill px-3 ${
                            isSelected
                                ? "btn-primary fw-semibold"
                                : "btn-outline-secondary text-light"
                        }`}
                    >
                        {opt.value}
                    </button>
                );
            })}
        </div>
    )
}