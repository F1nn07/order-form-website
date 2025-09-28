// Clear search
function clearSearch() {
    window.location.href = '/';
}
 
// Smooth scroll to top
function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Debounce function to limit how often a function is called
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

// Function to send form data to server for saving progress
function autoSave() {
    const customer_name = document.getElementById('customer_name_input').value;
    const customer_phone = document.getElementById('customer_phone_input').value;
    const room_number = document.getElementById('room_number_input').value;

    const quantities = {};
    document.querySelectorAll("input[name^='qty_']").forEach(input => {
        quantities[input.name] = input.value;
    });

    return fetch("/save-progress", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            customer_name,
            customer_phone,
            room_number,
            quantities
        })
    });
}

// Function to clear customer info and quantities from the session
function clearForm() {
    if (confirm("ნამდვილად გსურთ ფორმის გასუფთავება?")) {
        fetch("/clear-session", {
            method: "POST"
        }).then(response => {
            if (response.ok) {
                window.location.reload();
            }
        });
    }
}

// Function to handle the manual "Save" button click with visual feedback
function handleSaveClick() {
    const saveBtn = document.getElementById('saveBtn');
    if (!saveBtn) return;

    const originalHtml = saveBtn.innerHTML;
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>შენახვა...`; // Saving...
    saveBtn.classList.remove('bg-blue-500', 'hover:bg-blue-600');
    saveBtn.classList.add('bg-yellow-500', 'cursor-not-allowed');

    autoSave()
        .then(response => {
            if (response.ok) {
                saveBtn.innerHTML = `<i class="fas fa-check-circle mr-2"></i>შენახულია!`; // Saved!
                saveBtn.classList.remove('bg-yellow-500');
                saveBtn.classList.add('bg-green-500');
            } else {
                throw new Error('Server responded with an error.');
            }
        })
        .catch(error => {
            console.error('Save failed:', error);
            saveBtn.innerHTML = `<i class="fas fa-times-circle mr-2"></i>შეცდომა`; // Error
            saveBtn.classList.remove('bg-yellow-500');
            saveBtn.classList.add('bg-red-500');
        })
        .finally(() => {
            setTimeout(() => {
                saveBtn.innerHTML = originalHtml;
                saveBtn.disabled = false;
                saveBtn.classList.remove('bg-green-500', 'bg-red-500', 'bg-yellow-500', 'cursor-not-allowed');
                saveBtn.classList.add('bg-blue-500', 'hover:bg-blue-600');
            }, 2000);
        });
}

// Function to sync the main form inputs with the hidden search form inputs
function syncSearchForm() {
    const nameInput = document.getElementById('customer_name_input');
    const phoneInput = document.getElementById('customer_phone_input');
    const roomInput = document.getElementById('room_number_input');
    
    if (nameInput && phoneInput && roomInput) {
        document.getElementById('hidden_customer_name').value = nameInput.value;
        document.getElementById('hidden_customer_phone').value = phoneInput.value;
        document.getElementById('hidden_room_number').value = roomInput.value;
    }
}

// Animate scroll icon on scroll
window.addEventListener('scroll', () => {
    const scrollIcon = document.getElementById('scrollIcon');
    if (scrollIcon) {
        scrollIcon.classList.toggle('animate-pulse', window.scrollY > 300);
    }
});

// Auto-hide flash messages after 5 seconds
setTimeout(() => {
    document.querySelectorAll('.border-l-4, .animate-slideIn').forEach(alert => {
        alert.style.transition = 'opacity 0.5s ease';
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 500);
    });
}, 5000);

// Debounced version of autoSave for use with input events
const debouncedAutoSave = debounce(autoSave, 500);

// Add event listener to all relevant inputs for auto-saving
document.addEventListener('input', (event) => {
    if (event.target.matches("input[name^='customer_'], input[name^='qty_']")) {
        debouncedAutoSave();
    }
});

// A single listener for when the page content is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // 1. Sync forms on initial page load
    syncSearchForm();

    // 2. Force save before search to prevent data loss
    const searchForm = document.getElementById('searchForm');
    let isSearchSubmitting = false; // Flag to prevent infinite loop

    if (searchForm) {
        searchForm.addEventListener('submit', function(event) {
            if (isSearchSubmitting) return;
            
            event.preventDefault();
            autoSave().finally(() => {
                isSearchSubmitting = true;
                searchForm.submit();
            });
        });
    }

    // 3. Add validation for the main order form submission
    const orderForm = document.getElementById('orderForm');
    if (orderForm) {
        orderForm.addEventListener('submit', function(e) {
            let hasItems = false;
            document.querySelectorAll('.quantity-input').forEach(input => {
                if (parseInt(input.value) > 0) {
                    hasItems = true;
                }
            });

            if (!hasItems) {
                e.preventDefault();
                alert('გთხოვთ, შეარჩიოთ მინიმუმ ერთი ნივთი რაოდენობის შეყვანით (0-ზე მეტი).');
            }
        });
    }
});

// Add this function to your static/scripts.js file

function submitAction(action, itemId = null) {
    const form = document.getElementById('adminForm');
    const actionInput = document.getElementById('formAction');
    const itemIdInput = document.getElementById('formItemId');
    const itemNameInput = document.getElementById('formItemName');
    const bulkItemsInput = document.getElementById('formBulkItems');

    // Set the action for the form
    actionInput.value = action;

    if (action === 'add') {
        const name = document.getElementById('add_item_name').value;
        if (!name.trim()) {
            alert('Please enter an item name.');
            return;
        }
        itemNameInput.value = name;
    } else if (action === 'edit') {
        const name = document.getElementById('edit_name_input_' + itemId).value;
        if (!name.trim()) {
            alert('Please enter an item name.');
            return;
        }
        itemIdInput.value = itemId;
        itemNameInput.value = name;
    } else if (action === 'delete') {
        if (!confirm('Are you sure you want to delete this item?')) {
            return;
        }
        itemIdInput.value = itemId;
    } else if (action === 'bulk_add') {
        const bulkText = document.getElementById('bulk_items_textarea').value;
        if (!bulkText.trim()) {
            alert('Please enter items for bulk addition.');
            return;
        }
        bulkItemsInput.value = bulkText;
    }
    
    // Submit the form
    form.submit();
}