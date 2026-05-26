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

         / /   = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = 
         / /   1 1 .   P a y m e n t   M o d a l   L o g i c 
         / /   = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = 
         c o n s t   m o d a l   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' p a y m e n t - m o d a l ' ) ; 
         c o n s t   m o d a l C l o s e   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' m o d a l - c l o s e ' ) ; 
         c o n s t   b u y M o n t h l y   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' b u y - m o n t h l y ' ) ; 
         c o n s t   b u y L i f e t i m e   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' b u y - l i f e t i m e ' ) ; 
         c o n s t   b u y Y e a r l y   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' b u y - y e a r l y ' ) ; 
         c o n s t   m o d a l A m o u n t   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' m o d a l - a m o u n t ' ) ; 
         
         / /   W a l l e t s   ( P l a c e h o l d e r s   -   u s e r   n e e d s   t o   r e p l a c e   t h e s e   w i t h   a c t u a l   w a l l e t s ) 
         c o n s t   w a l l e t s   =   { 
                 t r c 2 0 :   ' T x x x x x x x x x x x x x x x x x x x x x x x x x x x x x x ' ,   / /   T r o n   U S D T 
                 b e p 2 0 :   ' 0 x x x x x x x x x x x x x x x x x x x x x x x x x x x x x x '     / /   B S C   U S D T 
         } ; 
 
         f u n c t i o n   o p e n M o d a l ( a m o u n t )   { 
                 i f ( m o d a l A m o u n t )   m o d a l A m o u n t . t e x t C o n t e n t   =   a m o u n t ; 
                 i f ( m o d a l )   m o d a l . c l a s s L i s t . a d d ( ' a c t i v e ' ) ; 
                 d o c u m e n t . b o d y . s t y l e . o v e r f l o w   =   ' h i d d e n ' ;   / /   P r e v e n t   s c r o l l i n g 
         } 
 
         f u n c t i o n   c l o s e M o d a l ( )   { 
                 i f ( m o d a l )   m o d a l . c l a s s L i s t . r e m o v e ( ' a c t i v e ' ) ; 
                 d o c u m e n t . b o d y . s t y l e . o v e r f l o w   =   ' ' ; 
         } 
 
         i f ( b u y M o n t h l y )   b u y M o n t h l y . a d d E v e n t L i s t e n e r ( ' c l i c k ' ,   ( e )   = >   {   e . p r e v e n t D e f a u l t ( ) ;   o p e n M o d a l ( ' 9 ' ) ;   } ) ; 
         i f ( b u y L i f e t i m e )   b u y L i f e t i m e . a d d E v e n t L i s t e n e r ( ' c l i c k ' ,   ( e )   = >   {   e . p r e v e n t D e f a u l t ( ) ;   o p e n M o d a l ( ' 4 9 ' ) ;   } ) ; 
         i f ( b u y Y e a r l y )   b u y Y e a r l y . a d d E v e n t L i s t e n e r ( ' c l i c k ' ,   ( e )   = >   {   e . p r e v e n t D e f a u l t ( ) ;   o p e n M o d a l ( ' 7 2 ' ) ;   } ) ; 
         
         i f ( m o d a l C l o s e )   m o d a l C l o s e . a d d E v e n t L i s t e n e r ( ' c l i c k ' ,   c l o s e M o d a l ) ; 
         
         / /   C l o s e   o n   o u t s i d e   c l i c k 
         i f ( m o d a l )   { 
                 m o d a l . a d d E v e n t L i s t e n e r ( ' c l i c k ' ,   ( e )   = >   { 
                         i f   ( e . t a r g e t   = = =   m o d a l )   c l o s e M o d a l ( ) ; 
                 } ) ; 
         } 
 
         / /   C r y p t o   T a b s   L o g i c 
         c o n s t   c r y p t o T a b s   =   d o c u m e n t . q u e r y S e l e c t o r A l l ( ' . c r y p t o - t a b ' ) ; 
         c o n s t   c r y p t o A d d r e s s   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' c r y p t o - a d d r e s s ' ) ; 
         c o n s t   a c t i v e N e t w o r k   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' a c t i v e - n e t w o r k ' ) ; 
 
         c r y p t o T a b s . f o r E a c h ( t a b   = >   { 
                 t a b . a d d E v e n t L i s t e n e r ( ' c l i c k ' ,   ( )   = >   { 
                         c r y p t o T a b s . f o r E a c h ( t   = >   t . c l a s s L i s t . r e m o v e ( ' a c t i v e ' ) ) ; 
                         t a b . c l a s s L i s t . a d d ( ' a c t i v e ' ) ; 
                         
                         c o n s t   n e t w o r k   =   t a b . g e t A t t r i b u t e ( ' d a t a - n e t w o r k ' ) ; 
                         i f   ( n e t w o r k   = = =   ' t r c 2 0 ' )   { 
                                 a c t i v e N e t w o r k . t e x t C o n t e n t   =   ' T r o n   N e t w o r k   ( T R C 2 0 ) ' ; 
                                 c r y p t o A d d r e s s . t e x t C o n t e n t   =   w a l l e t s . t r c 2 0 ; 
                         }   e l s e   i f   ( n e t w o r k   = = =   ' b e p 2 0 ' )   { 
                                 a c t i v e N e t w o r k . t e x t C o n t e n t   =   ' B N B   S m a r t   C h a i n   ( B E P 2 0 ) ' ; 
                                 c r y p t o A d d r e s s . t e x t C o n t e n t   =   w a l l e t s . b e p 2 0 ; 
                         } 
                 } ) ; 
         } ) ; 
 
         / /   C o p y   B u t t o n   L o g i c 
         c o n s t   c o p y B t n   =   d o c u m e n t . g e t E l e m e n t B y I d ( ' c o p y - b t n ' ) ; 
         i f ( c o p y B t n   & &   c r y p t o A d d r e s s )   { 
                 c o p y B t n . a d d E v e n t L i s t e n e r ( ' c l i c k ' ,   ( )   = >   { 
                         n a v i g a t o r . c l i p b o a r d . w r i t e T e x t ( c r y p t o A d d r e s s . t e x t C o n t e n t ) . t h e n ( ( )   = >   { 
                                 c o n s t   i c o n   =   c o p y B t n . q u e r y S e l e c t o r ( ' i ' ) ; 
                                 i c o n . c l a s s N a m e   =   ' f a - s o l i d   f a - c h e c k ' ; 
                                 c o p y B t n . c l a s s L i s t . a d d ( ' c o p i e d ' ) ; 
                                 
                                 s e t T i m e o u t ( ( )   = >   { 
                                         i c o n . c l a s s N a m e   =   ' f a - r e g u l a r   f a - c o p y ' ; 
                                         c o p y B t n . c l a s s L i s t . r e m o v e ( ' c o p i e d ' ) ; 
                                 } ,   2 0 0 0 ) ; 
                         } ) ; 
                 } ) ; 
         } 
  
 