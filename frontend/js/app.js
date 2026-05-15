// app.js
document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('hero-video');
    const navbar = document.getElementById('navbar');
    
    // 1. Handle video end state
    if (video) {
        video.addEventListener('ended', () => {
            // Pause on last frame (default behavior if no loop)
            // Add faded class for decreased opacity
            video.classList.add('faded');
        });

        // Ensure video plays (browsers sometimes block autoplay)
        video.play().catch(e => console.log("Autoplay blocked:", e));
    }

    // 2. Navbar scroll effect
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.style.background = 'rgba(0, 0, 0, 0.8)';
            navbar.style.padding = '1rem 4rem';
        } else {
            navbar.style.background = 'rgba(0, 0, 0, 0.2)';
            navbar.style.padding = '1.5rem 4rem';
        }
    });

    // 3. Simple Reveal on Scroll Animation
    const observerOptions = {
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .large-text-section').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(40px)';
        el.style.transition = 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(el);
    });
});
