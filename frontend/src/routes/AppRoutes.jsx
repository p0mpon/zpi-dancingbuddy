import {Routes, Route} from 'react-router-dom';

import AuthLayout from '../layouts/AuthLayout';

import UserDashboard from "../pages/UserDashboard";
import {LoginPage} from "../pages/Auth/LoginPage";
import RegisterPage from "../pages/Auth/RegisterPage";
import MainLayout from "../layouts/MainLayout";
import LoginRequiredRoute from "./LoginRequiredRoute";
import {Logout} from "../pages/Auth/Logout";
import Practice from "../pages/Practice";
import LearningLayout from "../layouts/LearningLayout";
import VideoListPage from "../pages/VideoListPage";

export default function AppRoutes() {
    return (
        <Routes>
            <Route element={<MainLayout showSearch={true}/>}>
                <Route path="/" element={<VideoListPage mode="general"/>}/>
                <Route element={<LoginRequiredRoute/>}>
                    <Route path="/my-videos" element={<VideoListPage mode="user_specific"/>}/>
                </Route>
            </Route>

            <Route element={<MainLayout showSearch={false}/>}>
                <Route element={<LoginRequiredRoute/>}>
                    <Route path="/account" element={<UserDashboard/>}/>
                </Route>
            </Route>

            <Route element={<LearningLayout/>}>
                <Route path="/video/:id" element={<Practice/>}/>
            </Route>

            <Route element={<AuthLayout/>}>
                <Route path="/register" element={<RegisterPage/>}/>
                <Route path="/login" element={<LoginPage/>}/>
                <Route path="/logout" element={<Logout/>}/>
            </Route>
        </Routes>
    )
        ;
}