import React, {useState} from 'react';
import {Container, Card, Form, Button, Alert, Spinner} from 'react-bootstrap';
import {Link, useNavigate} from 'react-router-dom';
import {useAuth} from "../../context/AuthContext";
import {loginUser, registerUser} from "../../api/calls";

export function LoginPage() {
    const [formData, setFormData] = useState({
        username: '',
        password: ''
    });
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const {login} = useAuth();
    const navigate = useNavigate();

    const handleChange = (e) => {
        setFormData({...formData, [e.target.name]: e.target.value});
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!formData.username || !formData.password) {
            setError('Please fill in all fields.');
            return;
        }

        setIsLoading(true);
        try {
            const userData = {
                username: formData.username,
                password: formData.password
            };

            await login(userData);
            navigate('/');
        } catch (err) {
            if (err.response?.status === 400) {
                setError(err.response.data.detail || "Invalid data provided.");
            } else if (err.response?.status === 500) {
                setError("Server is down. Please try again later.");
            } else {
                setError("Login failed.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Container className="d-flex align-items-center justify-content-center py-5">
            <Card bg="black" text="light" className="border-secondary shadow p-3"
                  style={{maxWidth: '420px', width: '100%'}}>
                <Card.Body>
                    <div className="text-center mb-4">
                        <h3 className="fw-bold">Sign in</h3>
                    </div>

                    {error && <Alert variant="danger" className="py-2 small">{error}</Alert>}

                    <Form onSubmit={handleSubmit}>
                        <Form.Group className="mb-3" controlId="loginUsername">
                            <Form.Label className="text-muted small">Username</Form.Label>
                            <Form.Control
                                type="text"
                                name="username"
                                value={formData.username}
                                onChange={handleChange}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-4" controlId="loginPassword">
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

                        <Button variant="primary" type="submit" className="w-100 fw-bold py-2 mb-3"
                                disabled={isLoading}>
                            {isLoading ? <Spinner size="sm" animation="border"/> : 'Sign In'}
                        </Button>
                    </Form>

                    <div className="text-center text-muted small">
                        Don't have an account?{' '}
                        <Link to="/register" className="text-primary text-decoration-none fw-semibold">
                            Register
                        </Link>
                    </div>
                </Card.Body>
            </Card>
        </Container>
    );
}