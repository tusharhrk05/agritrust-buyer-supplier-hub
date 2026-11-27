document.addEventListener('DOMContentLoaded', () => {
    const sections = ['crop', 'logistics', 'sustainability'];
    let currentStep = 0;
    const form = document.getElementById('listing-form');
    
    const prevBtn = document.getElementById('prev-btn');
    const submitBtn = document.getElementById('submit-btn');

    // --- Helper Functions ---

    // Gets all required inputs in the current section
    function getCurrentSectionRequiredInputs() {
        const sectionId = `section-${sections[currentStep]}`;
        const currentSection = document.getElementById(sectionId);
        // Selects required inputs, selects, and radio buttons within the current section
        return currentSection.querySelectorAll('[required]');
    }

    // Checks if a single input element has a valid, non-empty value
    function isInputValid(input) {
        if (input.type === 'radio') {
            // For radio buttons, check if at least one in the group is checked
            const groupName = input.name;
            const isChecked = document.querySelector(`input[name="${groupName}"]:checked`);
            return !!isChecked;
        } else if (input.tagName === 'SELECT') {
            // For select elements, check if the value is NOT empty/placeholder
            return input.value && input.value !== 'Select Crop Type' && input.value !== 'Select Variety' && input.value !== 'Select Quality Grade' && input.value !== 'Select Delivery Method';
        } else {
            // For text/number inputs
            return input.value.trim() !== '';
        }
    }

    // Checks if ALL required fields in the current section are filled
    function isSectionComplete() {
        const requiredInputs = getCurrentSectionRequiredInputs();
        for (let i = 0; i < requiredInputs.length; i++) {
            if (!isInputValid(requiredInputs[i])) {
                return false;
            }
        }
        return true;
    }

    // --- Navigation Logic ---

    function autoProgressForm() {
        if (isSectionComplete() && currentStep < sections.length - 1) {
            navigateStep(1);
        }
    }

    function navigateStep(direction) {
        // Apply completed status to the current step before moving forward
        if (direction > 0) {
            const currentCircle = document.getElementById(`step-${sections[currentStep]}-circle`);
            currentCircle.classList.add('completed-step');
        } else {
            // Remove completed status when moving backward
            const prevCircle = document.getElementById(`step-${sections[currentStep + direction]}-circle`);
            prevCircle.classList.remove('completed-step');
        }

        currentStep = Math.min(sections.length - 1, Math.max(0, currentStep + direction));

        updateStepIndicator();
        updateSectionVisibility();
        updateButtonState();

        // Scroll to the top of the form wrapper when section changes
        document.getElementById('listing-form').scrollIntoView({ behavior: 'smooth' });
        
        // After navigating, set focus to the first input of the new section
        const firstInput = getCurrentSectionRequiredInputs()[0];
        if (firstInput) {
            firstInput.focus();
        }
    }

    // --- State and View Updates ---

    function updateStepIndicator() {
        sections.forEach((section, index) => {
            const circle = document.getElementById(`step-${section}-circle`);
            const link = document.getElementById(`step-${section}-link`);

            // Set Active/Inactive classes
            if (index === currentStep) {
                link.classList.add('active');
                circle.classList.remove('inactive-step');
            } else {
                link.classList.remove('active');
            }

            // Ensure only future steps are visually inactive
            if (index > currentStep) {
                circle.classList.add('inactive-step');
            }
        });
    }

    function updateSectionVisibility() {
        sections.forEach((section, index) => {
            const sectionElement = document.getElementById(`section-${section}`);

            if (index === currentStep) {
                sectionElement.classList.remove('hidden-section');
                sectionElement.classList.add('current-section');
            } else {
                sectionElement.classList.add('hidden-section');
                sectionElement.classList.remove('current-section');
            }
        });
    }

    function updateButtonState() {
        // Handle Prev Button
        prevBtn.disabled = currentStep === 0;

        // Handle Submit Button
        if (currentStep === sections.length - 1) {
            submitBtn.classList.remove('hidden-section');
            // The Submit button should be enabled only if the last section is complete
            // For simplicity, we assume the user will validate on submission.
        } else {
            submitBtn.classList.add('hidden-section');
        }
    }

    // --- Event Listeners ---

    prevBtn.addEventListener('click', () => navigateStep(-1));

    // Listen to input changes and blur events on the entire form
    form.addEventListener('change', autoProgressForm);
    form.addEventListener('blur', (event) => {
        if (event.target.closest('.form-section.current-section')) {
            autoProgressForm();
        }
    }, true); // Use capture phase to catch events propagated through the form

    // Initialize the form state
    updateStepIndicator();
    updateSectionVisibility();
    updateButtonState();
});