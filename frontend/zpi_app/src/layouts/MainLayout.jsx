import { Outlet } from 'react-router-dom';
import {Container} from "react-bootstrap";
import TopBar from "../components/PageContent/TopBar";
import {useState} from "react";
import {VideoUploadModal} from "../components/Modals/VideoUploadModal";

export default function MainLayout({showSearch}) {
    const [showUpload, setShowUpload] = useState(false);
    return (
        <>
            <TopBar
            showSearch={showSearch}
            onOpenUpload={() => setShowUpload(true)}
            />
            <main className="main-content">
                <Container className="py-4">
                    <Outlet />
                </Container>
            </main>
            
            <VideoUploadModal
                show={showUpload}
                onClose={() => setShowUpload(false)}
                onUploadSuccess={() => setShowUpload(true)}
            />
        </>
    );
}