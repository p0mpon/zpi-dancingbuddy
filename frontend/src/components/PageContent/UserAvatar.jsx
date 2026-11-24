import {Image} from "react-bootstrap";
import React from "react";

export default function UserAvatar({avatarUrl, size}) {
    return (
        <div
            className="rounded-circle bg-secondary border border-secondary overflow-hidden d-flex align-items-center justify-content-center shadow-sm"
            style={{width: size, height: size}}
        >
            <Image
                src={avatarUrl ? avatarUrl : "https://placehold.co/100x100/3b82f6/ffffff?text=NA"}
                alt="User Avatar"
                fluid
            />
        </div>
    )
}