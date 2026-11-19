import {useEffect, useRef, useState} from "react";
import { useNavigate } from "react-router-dom";
import { Spinner } from "react-bootstrap";
import { useAuth } from "../../context/AuthContext";

export function Logout() {
    const { logout } = useAuth();
    const navigate = useNavigate();
    const [error, setError] = useState(null);
    const hasStarted = useRef(false);

    useEffect(() => {
        if (hasStarted.current) return;
        hasStarted.current = true;

        let timeoutId;

        const runLogout = async () => {
            try {
                await logout();
                navigate("/", { replace: true });
            } catch (err) {
                console.error("Logout failed:", err);
                setError("Couldn't complete logout on the server, redirecting...");
                timeoutId = setTimeout(() => {
                    navigate("/", { replace: true });
                }, 800);
            }
        };

        runLogout();

        return () => {
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, []);

    return (
        <div className="d-flex flex-column align-items-center justify-content-center py-5 gap-2">
            <Spinner animation="border" variant="light" size="sm" />
            <span className="text-muted small">{error || "Signing out..."}</span>
        </div>
    );
}