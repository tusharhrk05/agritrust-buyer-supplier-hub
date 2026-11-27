document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const messageDiv = document.getElementById('message');

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault(); // Prevent default form submission

        // Get form data
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;

        // Simple client-side validation
        if (!email || !password) {
            messageDiv.textContent = 'Please enter both email/username and password.';
            messageDiv.className = 'message error';
            return;
        }

        // Prepare data for the backend
        const loginData = {
            email: email,
            password: password
        };

        // Send data to the backend
        try {
            const response = await fetch('http://localhost:3000/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(loginData)
            });

            const data = await response.json();

            // Handle the response
            if (response.ok) {
                // Login successful
                messageDiv.textContent = data.message;
                messageDiv.className = 'message success';
                // You can redirect the user or perform other actions here
                // window.location.href = '/dashboard'; 
            } else {
                // Login failed
                messageDiv.textContent = data.message || 'Login failed. Please try again.';
                messageDiv.className = 'message error';
            }
        } catch (error) {
            console.error('Error during login:', error);
            messageDiv.textContent = 'An unexpected error occurred. Please try again later.';
            messageDiv.className = 'message error';
        }
    });
});