// GrootTrade Landing Page — Interactive Logic

document.addEventListener("DOMContentLoaded", () => {

    // =========================================
    // 1. Navbar Scroll Effect
    // =========================================
    const navbar = document.getElementById("navbar");

    function handleScroll() {
        if (window.scrollY > 60) {
            navbar.classList.add("scrolled");
        } else {
            navbar.classList.remove("scrolled");
        }
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    // =========================================
    // 2. Mobile Menu Toggle
    // =========================================
    const mobileToggle = document.getElementById("mobile-toggle");
    const navLinks = document.getElementById("nav-links");

    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener("click", () => {
            navLinks.classList.toggle("open");
            const icon = mobileToggle.querySelector("i");
            if (navLinks.classList.contains("open")) {
                icon.className = "fa-solid fa-xmark";
            } else {
                icon.className = "fa-solid fa-bars";
            }
        });

        // Close mobile menu on link click
        navLinks.querySelectorAll(".nav-link").forEach(link => {
            link.addEventListener("click", () => {
                navLinks.classList.remove("open");
                mobileToggle.querySelector("i").className = "fa-solid fa-bars";
            });
        });
    }

    // =========================================
    // 3. Smooth Scroll for Anchor Links
    // =========================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener("click", function (e) {
            const targetId = this.getAttribute("href");
            if (targetId === "#") return;
            
            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                const navHeight = navbar.offsetHeight;
                const targetPosition = target.getBoundingClientRect().top + window.scrollY - navHeight - 20;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: "smooth"
                });
            }
        });
    });

    // =========================================
    // 4. FAQ Accordion
    // =========================================
    const faqItems = document.querySelectorAll(".faq-item");

    faqItems.forEach(item => {
        const question = item.querySelector(".faq-question");
        
        question.addEventListener("click", () => {
            const isOpen = item.classList.contains("open");
            
            // Close all others
            faqItems.forEach(other => {
                other.classList.remove("open");
                other.querySelector(".faq-question").setAttribute("aria-expanded", "false");
            });
            
            // Toggle current
            if (!isOpen) {
                item.classList.add("open");
                question.setAttribute("aria-expanded", "true");
            }
        });
    });

    // =========================================
    // 5. Scroll-triggered Animations
    // =========================================
    const observerOptions = {
        root: null,
        rootMargin: "0px 0px -80px 0px",
        threshold: 0.1
    };

    const animateOnScroll = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add("revealed");
                animateOnScroll.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Add reveal animation to sections
    const revealElements = document.querySelectorAll(
        ".feature-card, .step-card, .risk-item, .pricing-card, .faq-item"
    );

    revealElements.forEach((el, index) => {
        el.style.opacity = "0";
        el.style.transform = "translateY(24px)";
        el.style.transition = `opacity 0.5s ease ${index % 3 * 0.1}s, transform 0.5s ease ${index % 3 * 0.1}s`;
        animateOnScroll.observe(el);
    });

    // CSS class for revealed state
    const style = document.createElement("style");
    style.textContent = `
        .revealed {
            opacity: 1 !important;
            transform: translateY(0) !important;
        }
    `;
    document.head.appendChild(style);

    // =========================================
    // 6. Active Nav Link Highlight
    // =========================================
    const sections = document.querySelectorAll("section[id]");
    const navLinksAll = document.querySelectorAll(".nav-link");

    function updateActiveLink() {
        const scrollPos = window.scrollY + navbar.offsetHeight + 100;

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.offsetHeight;
            const sectionId = section.getAttribute("id");

            if (scrollPos >= sectionTop && scrollPos < sectionTop + sectionHeight) {
                navLinksAll.forEach(link => {
                    link.classList.remove("active");
                    if (link.getAttribute("href") === `#${sectionId}`) {
                        link.classList.add("active");
                    }
                });
            }
        });
    }

    window.addEventListener("scroll", updateActiveLink, { passive: true });

    // =========================================
    // 7. Counter Animation for Stats
    // =========================================
    function animateValue(element, start, end, duration, suffix = "") {
        const range = end - start;
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(start + range * eased);
            
            element.textContent = current + suffix;
            
            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }

    // Animate hero stats when visible
    const heroStats = document.querySelector(".hero-stats");
    if (heroStats) {
        const statsObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Stats are text-based, no counter needed — already set in HTML
                    statsObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        statsObserver.observe(heroStats);
    }

    // =========================================
    // 8. Pricing Card Hover Glow Effect
    // =========================================
    const pricingCards = document.querySelectorAll(".pricing-card");

    pricingCards.forEach(card => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            card.style.setProperty("--mouse-x", `${x}px`);
            card.style.setProperty("--mouse-y", `${y}px`);
        });
    });

    // =========================================
    // 9. Signal Feed Animation Loop
    // =========================================
    const signalFeed = document.querySelector(".preview-signal-feed");
    if (signalFeed) {
        const symbols = ["XAUUSD", "EURUSD", "GBPJPY", "USDJPY", "AUDUSD", "NZDUSD", "USDCHF", "XAGUSD"];
        const actions = ["BUY", "SELL"];

        setInterval(() => {
            const entries = signalFeed.querySelectorAll(".signal-entry");
            if (entries.length > 0) {
                // Randomly pulse an entry
                const randomEntry = entries[Math.floor(Math.random() * entries.length)];
                randomEntry.style.borderColor = "rgba(0, 242, 254, 0.2)";
                setTimeout(() => {
                    randomEntry.style.borderColor = "";
                }, 1000);
            }
        }, 3000);
    }

    // =========================================
    // 10. Keyboard Accessibility
    // =========================================
    document.addEventListener("keydown", (e) => {
        // Escape closes mobile menu
        if (e.key === "Escape" && navLinks && navLinks.classList.contains("open")) {
            navLinks.classList.remove("open");
            mobileToggle.querySelector("i").className = "fa-solid fa-bars";
        }
    });

});
