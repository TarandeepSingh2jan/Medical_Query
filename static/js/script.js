
document.getElementById('queryForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const queryInput = document.getElementById('queryInput');
    const responseArea = document.getElementById('responseArea');
    const query = queryInput.value.trim();

    if (!query) {
        responseArea.textContent = 'Please enter a query.';
        responseArea.className = 'error';
        return;
    }

    responseArea.textContent = 'Processing...';
    responseArea.className = '';

    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });
        const data = await response.json();

        if (data.error) {
            responseArea.textContent = data.error;
            responseArea.className = 'error';
        } else if (data.warning) {
            responseArea.textContent = data.warning + ' Try a different disease name or consult a healthcare professional.';
            responseArea.className = 'warning';
        } else {
            responseArea.textContent = data.response;
            responseArea.className = '';
        }
    } catch (error) {
        responseArea.textContent = 'Error: Unable to process query. Please try again.';
        responseArea.className = 'error';
    }

    queryInput.value = '';
});