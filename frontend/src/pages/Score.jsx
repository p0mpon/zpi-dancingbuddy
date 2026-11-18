import React, { useEffect, useState } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { Spinner, Button } from 'react-bootstrap';
// Assuming you add this endpoint to fetch a past attempt by ID
import { getPastDanceAttempt } from '../api/calls';

export default function Score() {
    const { attemptId } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    const [scoreData, setScoreData] = useState(null);
    const [videoUrl, setVideoUrl] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        // If score data is present, use it directly
        if (location.state?.scoreData) {
            setScoreData(location.state.scoreData);
            setVideoUrl(location.state.localVideoUrl);
            setIsLoading(false);
            return;
        }

        // If not, fetch the score data from the backend
        let isMounted = true;

        getPastDanceAttempt(attemptId)
            .then(data => {
                if (isMounted) {
                    setScoreData(data);
                    // Assume the backend returns a URL to the saved video file
                    setVideoUrl(data.video_file_url);
                    setIsLoading(false);
                }
            })
            .catch(err => {
                console.error(err);
                if (isMounted) {
                    setError("Failed to load score data.");
                    setIsLoading(false);
                }
            });

        return () => { isMounted = false; };
    }, [attemptId, location.state]);

    if (isLoading) {
        return (
            <div className="vh-100 bg-black d-flex justify-content-center align-items-center">
                <Spinner animation="border" variant="light" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="vh-100 bg-black text-white d-flex flex-column justify-content-center align-items-center">
                <h3>{error}</h3>
                <Button variant="outline-light" className="mt-3" onClick={() => navigate('/')}>
                    Return to Menu
                </Button>
            </div>
        );
    }

    return (
        <div className="vh-100 bg-dark text-white p-4">
            <Button variant="link" className="text-light mb-4" onClick={() => navigate('/')}>
                &larr; Back to Menu
            </Button>

            <div className="row">
                <div className="col-md-6">
                    <video
                        src={videoUrl}
                        controls
                        className="w-100 rounded shadow"
                    />
                </div>
                <div className="col-md-6">
                    <h1 className="display-4 fw-bold">Score: {scoreData?.total_score || 0}</h1>
                    {/* TODO: Implement detailed score breakdown */}
                    <pre className="bg-black p-3 rounded mt-4 text-success">
                        {JSON.stringify(scoreData, null, 2)}
                    </pre>
                </div>
            </div>
        </div>
    );
}