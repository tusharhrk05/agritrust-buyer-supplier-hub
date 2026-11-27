// script.js

// The accordion functionality for the FAQ section is powered by the Alpine.js library,
// which is included in the index.html file.
// The logic is handled directly within the HTML using attributes like:
// - `x-data` to define a component's scope.
// - `@click` to handle user interaction.
// - `x-show` to toggle the visibility of the answer panels.

// This file can be used for any additional custom JavaScript you might need for your site.
// For example, you could add an event listener to a button:

/*
document.addEventListener('DOMContentLoaded', () => {
  // Example: Add a click event to the "Learn More" button
  const learnMoreButtons = document.querySelectorAll('.btn-secondary, .btn-hero-secondary');
  
  learnMoreButtons.forEach(button => {
    button.addEventListener('click', () => {
      // Smoothly scroll to the "Challenges" section
      const challengesSection = document.querySelector('#problems');
      if (challengesSection) {
        challengesSection.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
});
*/

console.log("Custom script file loaded successfully.");