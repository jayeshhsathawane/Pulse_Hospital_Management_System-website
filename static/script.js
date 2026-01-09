// pulsehospital/static/script.js

// ----------------------------------------------------------------------
// GLOBAL MODAL FUNCTIONS (These must be outside DOMContentLoaded)
// ----------------------------------------------------------------------

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeDoctorModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
}

function openGalleryModal(imageSrc) {
    const modal = document.getElementById('galleryModal');
    const modalImage = document.getElementById('galleryModalImage');
    if (modal && modalImage) {
        modalImage.src = imageSrc;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeGalleryModal() {
    const modal = document.getElementById('galleryModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
}

// Make critical functions globally available (NECESSARY for HTML onclick)
window.openDoctorModal = openModal;
window.closeDoctorModal = closeDoctorModal;
window.openGalleryModal = openGalleryModal;
window.closeGalleryModal = closeGalleryModal;


// Close modal listeners (kept global)
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal') && e.target.classList.contains('active')) {
        e.target.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const activeModal = document.querySelector('.modal.active');
        if (activeModal) {
            activeModal.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    }
});


// ----------------------------------------------------------------------
// MAIN EXECUTION LOGIC (Runs after all HTML is loaded)
// ----------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {

    // ----------------------------------------------------------------------
    // 1. MOBILE MENU TOGGLE FIX (Ensure elements are found here)
    // ----------------------------------------------------------------------
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    const navMenu = document.querySelector('.nav-menu');

    if (mobileMenuToggle && navMenu) {
        // FIX: The core toggle logic
        mobileMenuToggle.addEventListener('click', () => {
            navMenu.classList.toggle('active');
        });
        
        // Close menu when a link is clicked
        const navLinks = document.querySelectorAll('.nav-menu a');
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                navMenu.classList.remove('active');
            });
        });
    }


    // ----------------------------------------------------------------------
    // 2. SMOOTH SCROLLING (FOR ANCHORS LIKE #APPOINTMENT)
    // ----------------------------------------------------------------------
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            if (this.getAttribute('href').length > 1) { 
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    // ----------------------------------------------------------------------
    // 3. DOCTOR MODAL ACTIVATION FIX (Event Listener)
    // ----------------------------------------------------------------------
    const doctorProfileButtons = document.querySelectorAll('.doctor-card .view-profile-btn');
    
    doctorProfileButtons.forEach(button => {
        
        let modalId = button.getAttribute('data-modal-id'); 

        if (!modalId) {
            const onclickAttr = button.getAttribute('onclick');
            if (onclickAttr) {
                const modalMatch = onclickAttr.match(/'([^']+)'/); 
                if (modalMatch && modalMatch.length > 1) {
                    modalId = modalMatch[1];
                }
            }
        }
        
        if (modalId) {
            button.addEventListener('click', (e) => {
                e.stopPropagation();
                if (window.openModal) {
                    window.openModal(modalId);
                }
            });
        }
    });

    // ----------------------------------------------------------------------
    // 4. GALLERY MODAL ACTIVATION FIX
    // ----------------------------------------------------------------------
    const galleryItems = document.querySelectorAll('.gallery-item');
    galleryItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            
            const onclickAttr = item.getAttribute('onclick');
            if (onclickAttr) {
                const srcMatch = onclickAttr.match(/'([^']+)'/);
                if (srcMatch && srcMatch.length > 1) {
                    const imageSrc = srcMatch[1];
                    openGalleryModal(imageSrc);
                }
            }
        });
    });


    // ----------------------------------------------------------------------
    // 5. TESTIMONIALS CAROUSEL
    // ----------------------------------------------------------------------
    let currentTestimonial = 0;
    const testimonials = document.querySelectorAll('.testimonial-card');
    const prevBtn = document.querySelector('.carousel-btn.prev');
    const nextBtn = document.querySelector('.carousel-btn.next');

    function showTestimonial(index) {
        testimonials.forEach((testimonial, i) => {
            testimonial.classList.remove('active');
            if (i === index) {
                testimonial.classList.add('active');
            }
        });
    }

    if (prevBtn && nextBtn && testimonials.length > 0) {
        showTestimonial(currentTestimonial);
        
        prevBtn.addEventListener('click', () => {
            currentTestimonial = (currentTestimonial - 1 + testimonials.length) % testimonials.length;
            showTestimonial(currentTestimonial);
        });

        nextBtn.addEventListener('click', () => {
            currentTestimonial = (currentTestimonial + 1) % testimonials.length;
            showTestimonial(currentTestimonial);
        });

        setInterval(() => {
            currentTestimonial = (currentTestimonial + 1) % testimonials.length;
            showTestimonial(currentTestimonial);
        }, 5000);
    }
    
    // ----------------------------------------------------------------------
    // 6. NAVBAR SCROLL EFFECT
    // ----------------------------------------------------------------------
    const navbar = document.querySelector('.navbar');

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        if (currentScroll > 100) {
            navbar.style.boxShadow = '0 4px 20px rgba(46, 204, 113, 0.15)';
        } else {
            navbar.style.boxShadow = '0 2px 15px rgba(46, 204, 113, 0.1)';
        }
    });
    
    console.log('Pulse Multispeciality Hospital Bhandara - JavaScript Core Initialized');
});



