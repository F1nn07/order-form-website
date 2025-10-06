// ============================================================================
// GLOBAL HELPER FUNCTIONS
// ============================================================================

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

// ============================================================================
// MAIN SCRIPT LOGIC
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {

    // ------------------------------------------------------------------------
    // LOGIC FOR THE MAIN ORDER PAGE (index.html)
    // ------------------------------------------------------------------------
    const orderForm = document.getElementById('orderForm');
    if (orderForm) {
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
                body: JSON.stringify({ customer_name, customer_phone, room_number, quantities })
            });
        }

        const debouncedAutoSave = debounce(autoSave, 500);
        document.addEventListener('input', (event) => {
            if (event.target.matches("#customer_name_input, #customer_phone_input, #room_number_input, input[name^='qty_']")) {
                debouncedAutoSave();
            }
        });

        const itemSelector = document.getElementById('item-select');
        const selectedItemsTable = document.getElementById('selected-items-table');

        if (itemSelector && selectedItemsTable) {
            function addQuantityRow(itemId, itemName, quantity = 1) {
                const newRow = document.createElement('tr');
                newRow.id = `selected-item-row-${itemId}`;
                newRow.className = 'fade-in-up';
                newRow.innerHTML = `
                    <td class="py-4 border-b border-gray-200"><p class="font-semibold text-gray-800">${itemName}</p></td>
                    <td class="py-4 border-b border-gray-200 w-40 text-right">
                        <input type="number" name="qty_${itemId}" min="1" value="${quantity}" class="quantity-input w-20 h-12 text-center text-lg font-medium">
                        <span class="text-gray-500 font-medium">ცალი</span>
                    </td>`;
                selectedItemsTable.appendChild(newRow);
            }

            // --- UPDATED: Preload items from data attribute for instant display and local search ---
            const allItemsData = JSON.parse(itemSelector.dataset.items || '[]');
            console.log('Total items loaded:', allItemsData.length); 
            const tomselect = new TomSelect('#item-select', {
                plugins: ['remove_button'],
                valueField: 'id',
                labelField: 'name',
                searchField: 'name',
                options: allItemsData,
                maxOptions: null,
                sortField: {
                    field: 'name',
                    direction: 'asc'
                },
                onItemAdd: function(value, $item) {
                    const itemName = this.options[value].name;
                    addQuantityRow(value, itemName);
                    toggleClearButton();
                },
                onItemRemove: function(value) {
                    const rowToRemove = document.getElementById(`selected-item-row-${value}`);
                    if (rowToRemove) rowToRemove.remove();
                    toggleClearButton();
                }
            });

            // Create Clear All button
            const clearAllBtn = document.createElement('button');
            clearAllBtn.type = 'button';
            clearAllBtn.id = 'clearAllItemsBtn';
            clearAllBtn.className = 'clear-all-btn hidden';
            clearAllBtn.innerHTML = '<i class="fas fa-times-circle mr-2"></i>ყველას წაშლა';
            
            // Insert button after the item selector
            itemSelector.parentElement.appendChild(clearAllBtn);
            
            // Show/hide button based on selected items
            function toggleClearButton() {
                const hasItems = tomselect.items.length > 0;
                clearAllBtn.classList.toggle('hidden', !hasItems);
            }
            
            // Clear all functionality
            clearAllBtn.addEventListener('click', function() {
                if (confirm('ნამდვილად გსურთ ყველა ნივთის წაშლა?')) {
                    tomselect.clear();
                    selectedItemsTable.innerHTML = '';
                    toggleClearButton();
                    debouncedAutoSave();
                }
            });

            // --- Restore saved state on page load ---
            if (typeof formData !== 'undefined' && formData && formData.quantities) {
                const itemMap = new Map(allItemsData.map(item => [item.id.toString(), item.name]));
                for (const key in formData.quantities) {
                    const itemId = key.replace('qty_', '');
                    const quantity = formData.quantities[key];
                    if (quantity > 0) {
                        const itemName = itemMap.get(itemId);
                        if (itemName) {
                            tomselect.addOption({id: itemId, name: itemName});
                            tomselect.addItem(itemId, true);
                            addQuantityRow(itemId, itemName, quantity);
                        }
                    }
                }
            } else {
                fetch('/clear-session', { method: 'POST' });
            }
            
            // Initial check for button visibility
            toggleClearButton();
        }
    }

    // ------------------------------------------------------------------------
    // LOGIC FOR THE ADMIN PANEL PAGE (admin_panel.html)
    // ------------------------------------------------------------------------
    const adminPanel = document.getElementById('addItemForm');
    if (adminPanel) {
        const newItemNameInput = document.getElementById('newItemName');
        const itemList = document.getElementById('itemList');

        function updateItemCounts() {
            if (!itemList) return;
            const countHeader = document.getElementById('item-count-header');
            const countStat = document.getElementById('item-count-stat');
            if (countHeader && countStat) {
                const newCount = itemList.children.length;
                countStat.innerText = newCount;
                countHeader.innerHTML = `<i class="fas fa-list mr-3 text-cyan-500"></i> ნივთები (${newCount})`;
            }
        }

        adminPanel.addEventListener('submit', (e) => {
            e.preventDefault();
            const itemName = newItemNameInput.value.trim();
            if (itemName) {
                fetch('/api/item/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: itemName })
                })
                .then(r => r.json()).then(data => {
                    if (data.status === 'success') {
                        if (itemList) {
                            const newRow = itemList.insertRow(0);
                            newRow.id = `item-row-${data.item.id}`;
                            newRow.innerHTML = `
                                <td class="px-6 py-4 whitespace-nowrap"><input type="text" value="${data.item.name}" class="edit-item-input bg-transparent border-b w-full" data-id="${data.item.id}"></td>
                                <td class="px-6 py-4 whitespace-nowrap text-right">
                                    <button class="save-item-btn text-blue-600 hidden" data-id="${data.item.id}" title="Save"><i class="fas fa-save"></i></button>
                                    <button class="delete-item-btn text-red-600" data-id="${data.item.id}" title="Delete"><i class="fas fa-trash"></i></button>
                                </td>`;
                            newItemNameInput.value = '';
                            updateItemCounts();
                        }
                    } else {
                        alert(data.message || 'Error adding item');
                    }
                }).catch(err => alert('An error occurred.'));
            }
        });

        // Bulk Add Form Logic
        const bulkAddForm = document.getElementById('bulkAddForm');
        if (bulkAddForm) {
            bulkAddForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const bulkText = document.getElementById('bulkItemsText').value.trim();
                const submitButton = bulkAddForm.querySelector('button[type="submit"]');
                const originalButtonHtml = submitButton.innerHTML;
                submitButton.disabled = true;
                submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> მუშაობს...';

                fetch('/api/item/bulk_add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ items_text: bulkText })
                }).then(r => r.json()).then(data => {
                    alert(data.message);
                    if (data.status === 'success') { window.location.reload(); }
                }).catch(err => alert('An error occurred.'))
                .finally(() => {
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalButtonHtml;
                });
            });
        }
        
        const liveSearchInput = document.getElementById('liveSearchInput');
        if (liveSearchInput) {
            const debouncedSearch = debounce(() => {
                const query = liveSearchInput.value.trim();
                const paginationNav = document.querySelector('nav[aria-label="Page navigation"]');
                const countHeader = document.getElementById('item-count-header');
                if (query === '') {
                    window.location.href = '/admin/';
                    return;
                }
                fetch(`/api/items/search?q=${encodeURIComponent(query)}`)
                    .then(r => r.json()).then(items => {
                        if (itemList) itemList.innerHTML = '';
                        if (paginationNav) paginationNav.style.display = 'none';
                        items.forEach(item => {
                            const newRow = itemList.insertRow();
                            newRow.id = `item-row-${item.id}`;
                            newRow.innerHTML = `
                                <td class="px-6 py-4 whitespace-nowrap"><input type="text" value="${item.name}" class="edit-item-input bg-transparent border-b w-full" data-id="${item.id}"></td>
                                <td class="px-6 py-4 whitespace-nowrap text-right">
                                    <button class="save-item-btn text-blue-600 hidden" data-id="${item.id}" title="Save"><i class="fas fa-save"></i></button>
                                    <button class="delete-item-btn text-red-600" data-id="${item.id}" title="Delete"><i class="fas fa-trash"></i></button>
                                </td>`;
                        });
                        if (countHeader) {
                            countHeader.innerHTML = `<i class="fas fa-list mr-3 text-cyan-500"></i> Found ${items.length} items`;
                        }
                    });
            }, 300);
            liveSearchInput.addEventListener('input', debouncedSearch);
        }

        if (itemList) {
            itemList.addEventListener('click', (e) => {
                const deleteBtn = e.target.closest('.delete-item-btn');
                const saveBtn = e.target.closest('.save-item-btn');
                if (deleteBtn) {
                    const itemId = deleteBtn.dataset.id;
                    if (confirm('Are you sure?')) {
                        fetch(`/api/item/delete/${itemId}`, { method: 'DELETE' }).then(r => r.json()).then(data => {
                            if (data.status === 'success') {
                                document.getElementById(`item-row-${itemId}`).remove();
                                updateItemCounts();
                            } else { alert(`Error: ${data.message}`); }
                        });
                    }
                }
                if (saveBtn) {
                    const itemId = saveBtn.dataset.id;
                    const inputField = document.querySelector(`.edit-item-input[data-id='${itemId}']`);
                    const newName = inputField.value.trim();
                    fetch(`/api/item/edit/${itemId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: newName })
                    }).then(r => r.json()).then(data => {
                        if (data.status === 'success') {
                            saveBtn.classList.add('hidden');
                        } else { alert(`Error: ${data.message}`); }
                    });
                }
            });
            itemList.addEventListener('input', (e) => {
                if (e.target.classList.contains('edit-item-input')) {
                    const itemId = e.target.dataset.id;
                    const saveBtn = document.querySelector(`.save-item-btn[data-id='${itemId}']`);
                    if (saveBtn) saveBtn.classList.remove('hidden');
                }
            });
        }
    }

    // ------------------------------------------------------------------------
    // LOGIC FOR ALL PAGES
    // ------------------------------------------------------------------------
    setTimeout(() => {
        document.querySelectorAll('.flash-message').forEach(alert => {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        });
    }, 5000);

    const scrollIcon = document.getElementById('scrollIcon');
    if (scrollIcon) {
        window.addEventListener('scroll', () => {
            scrollIcon.classList.toggle('animate-pulse', window.scrollY > 300);
        });
    }
});