document.addEventListener('DOMContentLoaded', (event) => {
    const button = document.querySelector('#stateSelectorButton');
    const contentArea = document.querySelector('#googleMapBox');

    button.addEventListener("click", () => {
        const dropdown = document.querySelector('#stateSelector');
        const page = dropdown.value;

        contentArea.src = page;
    });
});