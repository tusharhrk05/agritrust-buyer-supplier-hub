document.addEventListener('DOMContentLoaded', () => {
    const filters = {
        cropType: document.getElementById('crop-type-filter'),
        minQuantity: document.getElementById('min-quantity'),
        location: document.getElementById('location-filter'),
        residue: document.querySelectorAll('input[name="residue-filter"]')
    };

    const listingsGrid = document.querySelector('.listings-grid');
    const clearButton = document.querySelector('.clear-filters-btn');

    // --- Core Filtering Logic (Placeholder) ---
    function applyFilters() {
        const selectedCrop = filters.cropType.value;
        const minQty = parseInt(filters.minQuantity.value) || 0;
        const selectedLocation = filters.location.value.toLowerCase();
        
        let residueStatus = null;
        filters.residue.forEach(radio => {
            if (radio.checked) {
                residueStatus = radio.value;
            }
        });

        // In a real application, you would send these values to a server 
        // to fetch matching listings and update the listingsGrid.
        console.log({
            crop: selectedCrop,
            quantity: minQty,
            location: selectedLocation,
            residue: residueStatus
        });

        // For demo: Show status update
        const heading = document.querySelector('.listings-heading');
        heading.textContent = `Available Listings (Filtering active: ${selectedCrop || 'All'})`;
    }

    // --- Event Handlers ---
    
    // Apply filters instantly on select change or input blur
    filters.cropType.addEventListener('change', applyFilters);
    filters.minQuantity.addEventListener('blur', applyFilters);
    filters.location.addEventListener('blur', applyFilters);
    filters.residue.forEach(radio => {
        radio.addEventListener('change', applyFilters);
    });


    // Clear all filters
    clearButton.addEventListener('click', () => {
        filters.cropType.value = "";
        filters.minQuantity.value = "";
        filters.location.value = "";
        filters.residue.forEach(radio => {
            radio.checked = false;
        });
        applyFilters();
        const heading = document.querySelector('.listings-heading');
        heading.textContent = `Available Listings (248)`;
    });
});