import React from "react";
import {useVideo} from "../../../../context/VideoContext";

export default function DetailsTab() {
    const {currentVideo} = useVideo();

    return (
        <div className="overflow-y-auto pe-2" style={{maxHeight: '460px'}}>
            <p className="text-light mb-1">Song title: {currentVideo.song_title}</p>
            <p className="text-light fs-6 mb-4">
                Artist: {currentVideo.song_author}
            </p>

            <div className="mb-3">
                <span className="text-secondary fw-semibold">Difficulty: </span>
                <span className="text-light">{currentVideo.difficulty}</span>
            </div>

            <hr className="border-secondary opacity-25 my-3"/>

            <div>
                <h6 className="text-secondary text-uppercase fs-6 fw-semibold mb-2">Description</h6>
                <p className="text-light opacity-75">
                    {currentVideo.description || "No description provided."}
                </p>
            </div>
        </div>

    )
}