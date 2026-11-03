import React from 'react';
import AppRoutes from "./routes/AppRoutes";
import {BrowserRouter} from "react-router-dom";
import './App.css';
import {AuthProvider} from "./context/AuthContext";


export default function App() {
    return (
        <AuthProvider>
            <div className="app-container bg-dark text-light min-vh-100 pb-5">
                <BrowserRouter>
                    <AppRoutes />
                </BrowserRouter>
            </div>
        </AuthProvider>
    );
}