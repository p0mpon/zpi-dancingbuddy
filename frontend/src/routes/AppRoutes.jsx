import {Routes, Route} from 'react-router-dom';

import AuthLayout from '../layouts/AuthLayout';

import VideoList from "../pages/VideoList";
import UserDashboard from "../pages/UserDashboard";
import {LoginPage} from "../pages/Auth/LoginPage";
import RegisterPage from "../pages/Auth/RegisterPage";
import MainLayout from "../layouts/MainLayout";
import LoginRequiredRoute from "./LoginRequiredRoute";
import {Logout} from "../pages/Auth/Logout";
import Practice from "../pages/Practice";

export default function AppRoutes() {
    return (
        <Routes>
            <Route element={<MainLayout showSearch={true}/>}>
                <Route path="/" element={<VideoList/>}/>
                <Route path="/video/:id" element={<Practice/>}/>
            </Route>

            <Route element={<MainLayout showSearch={false}/>}>
                <Route element={<LoginRequiredRoute/>}>
                    <Route path="/account" element={<UserDashboard/>}/>
                </Route>
            </Route>


            <Route element={<AuthLayout/>}>
                <Route path="/register" element={<RegisterPage/>}/>
                <Route path="/login" element={<LoginPage/>}/>
                <Route path="/logout" element={<Logout/>}/>
            </Route>
        </Routes>
    );
}