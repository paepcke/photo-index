/**
 * Autocomplete component for search fields
 * Fetches suggestions from backend /facets/ endpoint
 */

class Autocomplete {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.fields = options.fields || ['description_parsed.objects'];
        this.minChars = options.minChars || 2;
        this.debounceMs = options.debounceMs || 300;
        this.maxResults = options.maxResults || 10;
        
        this.dropdown = null;
        this.debounceTimer = null;
        this.cache = {};
        this.currentFocus = -1;
        
        this.init();
    }
    
    init() {
        // Create dropdown element
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'autocomplete-dropdown';
        this.dropdown.style.display = 'none';
        this.input.parentNode.style.position = 'relative';
        this.input.parentNode.appendChild(this.dropdown);
        
        // Bind events
        this.input.addEventListener('input', (e) => this.onInput(e));
        this.input.addEventListener('keydown', (e) => this.onKeyDown(e));
        this.input.addEventListener('blur', () => {
            // Delay to allow click on dropdown
            setTimeout(() => this.hideDropdown(), 200);
        });
        
        // Close on click outside
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.dropdown.contains(e.target)) {
                this.hideDropdown();
            }
        });
    }
    
    onInput(e) {
        const value = e.target.value.trim();
        
        // Clear timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        
        // Hide if too short
        if (value.length < this.minChars) {
            this.hideDropdown();
            return;
        }
        
        // Debounce
        this.debounceTimer = setTimeout(() => {
            this.fetchSuggestions(value);
        }, this.debounceMs);
    }
    
    async fetchSuggestions(query) {
        const queryLower = query.toLowerCase();
        
        // Check cache first
        const cacheKey = this.fields.join(',');
        if (this.cache[cacheKey]) {
            this.filterAndShow(this.cache[cacheKey], queryLower);
            return;
        }
        
        // Fetch from all fields
        try {
            const allValues = new Set();
            
            for (const field of this.fields) {
                const response = await fetch(`/facets/${encodeURIComponent(field)}?limit=10000`);
                if (!response.ok) continue;

                const data = await response.json();
                Object.keys(data).forEach(value => allValues.add(value));
            }
            
            // Cache results
            this.cache[cacheKey] = Array.from(allValues);
            
            // Filter and show
            this.filterAndShow(this.cache[cacheKey], queryLower);
            
        } catch (error) {
            console.error('Autocomplete fetch error:', error);
        }
    }
    
    filterAndShow(values, query) {
        // Filter values that contain query
        const matches = values
            .filter(v => v.toLowerCase().includes(query))
            .sort((a, b) => {
                // Prioritize matches at start
                const aStarts = a.toLowerCase().startsWith(query);
                const bStarts = b.toLowerCase().startsWith(query);
                if (aStarts && !bStarts) return -1;
                if (!aStarts && bStarts) return 1;
                return a.localeCompare(b);
            })
            .slice(0, this.maxResults);
        
        if (matches.length === 0) {
            this.hideDropdown();
            return;
        }
        
        this.showDropdown(matches, query);
    }
    
    showDropdown(suggestions, query) {
        this.dropdown.innerHTML = '';
        this.currentFocus = -1;
        
        suggestions.forEach((suggestion, index) => {
            const item = document.createElement('div');
            item.className = 'autocomplete-item';
            
            // Highlight matching part
            const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
            item.innerHTML = suggestion.replace(regex, '<strong>$1</strong>');
            
            item.addEventListener('click', () => {
                this.selectValue(suggestion);
            });
            
            this.dropdown.appendChild(item);
        });
        
        this.dropdown.style.display = 'block';
    }
    
    hideDropdown() {
        this.dropdown.style.display = 'none';
        this.currentFocus = -1;
    }
    
    selectValue(value) {
        this.input.value = value;
        this.hideDropdown();
        this.input.focus();
        
        // Trigger change event
        const event = new Event('change', { bubbles: true });
        this.input.dispatchEvent(event);
    }
    
    onKeyDown(e) {
        if (this.dropdown.style.display === 'none') return;
        
        const items = this.dropdown.getElementsByClassName('autocomplete-item');
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.currentFocus++;
            if (this.currentFocus >= items.length) this.currentFocus = 0;
            this.setActive(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.currentFocus--;
            if (this.currentFocus < 0) this.currentFocus = items.length - 1;
            this.setActive(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (this.currentFocus > -1 && items[this.currentFocus]) {
                items[this.currentFocus].click();
            }
        } else if (e.key === 'Escape') {
            this.hideDropdown();
        }
    }
    
    setActive(items) {
        // Remove active from all
        Array.from(items).forEach(item => item.classList.remove('active'));
        
        // Add active to current
        if (this.currentFocus >= 0 && this.currentFocus < items.length) {
            items[this.currentFocus].classList.add('active');
            items[this.currentFocus].scrollIntoView({ block: 'nearest' });
        }
    }
    
    escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
}

// Make available globally
window.Autocomplete = Autocomplete;
