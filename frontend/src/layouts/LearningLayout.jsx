import { Outlet } from 'react-router-dom';
import {Container} from "react-bootstrap";

export default function LearningLayout() {
    return (
        <>
            <main className="main-content">
                <Container className="py-4">
                    <Outlet />
                </Container>
            </main>
        </>
    );
}