import React, {useState} from 'react';
import {Container, Card, Form, Button, Alert, Spinner} from 'react-bootstrap';
import {Link, useNavigate} from 'react-router-dom';
import {useAuth} from "../../context/AuthContext";

export default function RegisterPage() {
    const [formData, setFormData] = useState({
        username: '',
        nickname: '',
        password: '',
        confirmPassword: ''
    });
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const {register} = useAuth();
    const navigate = useNavigate();

    const handleChange = (e) => {
        setFormData({...formData, [e.target.name]: e.target.value});
    };

    const validateForm = () => {
        const {username, nickname, password, confirmPassword} = formData;

        if (!username || !nickname || !password || !confirmPassword) {
            return 'Please fill in all fields.';
        }

        const usernameRegex = /^[a-zA-Z0-9~!@#$^*{}|:?`_\-\[\];',.\/]{6,32}$/;
        if (!usernameRegex.test(username)) {
            return 'Username must be 6-32 characters long and contain only allowed letters, numbers, or special characters.';
        }

        const nicknameRegex = /^[a-zA-Z0-9._]{3,32}$/;
        if (!nicknameRegex.test(nickname)) {
            return 'Nickname must be 3-32 characters long and contain only letters, numbers, dots (.), or underscores (_).';
        }

        if (password.length < 12 || password.length > 32) {
            return 'Password must be between 12 and 32 characters.';
        }

        const passwordAllowedChars = /^[a-zA-Z0-9~!@#$^*{}|:?`\-\=\[\];',.\/]+$/;
        if (!passwordAllowedChars.test(password)) {
            return 'Password contains forbidden characters.';
        }

        if (!/(?=.*[A-Z])/.test(password)) return 'Password must contain at least one uppercase letter.';
        if (!/(?=.*[a-z])/.test(password)) return 'Password must contain at least one lowercase letter.';
        if (!/(?=.*\d)/.test(password)) return 'Password must contain at least one number.';
        if (!/(?=.*[~!@#$^*{}|:?`\-\=\[\];',.\/])/.test(password)) {
            return 'Password must contain at least one allowed special character.';
        }

        if (password !== confirmPassword) {
            return 'Passwords do not match.';
        }

        return null;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        const validationError = validateForm();
        if (validationError) {
            setError(validationError);
            return;
        }

        setError('');
        setIsLoading(true);

        try {
            const userData = {
                nickname: formData.nickname,
                username: formData.username,
                password: formData.password
            };
            
            await register(userData);
            navigate('/');
        } catch (err) {
            if (err.response?.status === 400) {
                setError(err.response.data.detail || "Invalid data provided (your username or nickname might be taken!).");
            } else if (err.response?.status === 500) {
                setError("Server is down. Please try again later.");
            } else {
                console.error(err);
                setError("Registration failed.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Container className="d-flex align-items-center justify-content-center py-5">
            <Card bg="black" text="light" className="border-secondary shadow p-3"
                  style={{maxWidth: '440px', width: '100%'}}>
                <Card.Body>
                    <div className="text-center mb-4">
                        <h3 className="fw-bold">Create Account</h3>
                    </div>

                    {error && <Alert variant="danger" className="py-2 small">{error}</Alert>}

                    <Form onSubmit={handleSubmit}>
                        <Form.Group className="mb-3" controlId="regUsername">
                            <Form.Label className="text-muted small">Username</Form.Label>
                            <Form.Control
                                type="text"
                                name="username"
                                value={formData.username}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-3" controlId="regNickname">
                            <Form.Label className="text-muted small">Nickname</Form.Label>
                            <Form.Control
                                type="text"
                                name="nickname"
                                value={formData.nickname}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-3" controlId="regPassword">
                            <Form.Label className="text-muted small">Password</Form.Label>
                            <Form.Control
                                type="password"
                                name="password"
                                placeholder="••••••••"
                                value={formData.password}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-4" controlId="regConfirmPassword">
                            <Form.Label className="text-muted small">Confirm Password</Form.Label>
                            <Form.Control
                                type="password"
                                name="confirmPassword"
                                placeholder="••••••••"
                                value={formData.confirmPassword}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Button variant="primary" type="submit" className="w-100 fw-bold py-2 mb-3"
                                disabled={isLoading}>
                            {isLoading ? <Spinner size="sm" animation="border"/> : 'Create Account'}
                        </Button>
                    </Form>

                    <div className="text-center text-muted small">
                        Already have an account?{' '}
                        <Link to="/login" className="text-primary text-decoration-none fw-semibold">
                            Sign In
                        </Link>
                    </div>
                </Card.Body>
            </Card>
        </Container>
    );
}