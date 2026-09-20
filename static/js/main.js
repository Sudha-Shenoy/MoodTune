/**
 * MoodTune - Client-Side JavaScript
 * Module 02: Landing Page UI/UX Micro-Interactions
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Mobile Navigation Toggle
    const mobileMenuToggle = document.getElementById("mobileMenuToggle");
    const navLinks = document.getElementById("navLinks");

    if (mobileMenuToggle && navLinks) {
        mobileMenuToggle.addEventListener("click", () => {
            const isExpanded = mobileMenuToggle.getAttribute("aria-expanded") === "true";
            mobileMenuToggle.setAttribute("aria-expanded", String(!isExpanded));
            navLinks.classList.toggle("open");
        });

        // Close mobile menu when clicking any nav link
        navLinks.querySelectorAll("a").forEach((link) => {
            link.addEventListener("click", () => {
                if (navLinks.classList.contains("open")) {
                    navLinks.classList.remove("open");
                    mobileMenuToggle.setAttribute("aria-expanded", "false");
                }
            });
        });
    }

    // 2. Floating Music Player - Play / Pause Visual Toggle
    const previewPlayBtn = document.getElementById("previewPlayBtn");
    const equalizerWrapper = document.querySelector(".equalizer-wrapper");

    if (previewPlayBtn && equalizerWrapper) {
        const playIcon = previewPlayBtn.querySelector(".play-icon");
        const pauseIcon = previewPlayBtn.querySelector(".pause-icon");

        previewPlayBtn.addEventListener("click", () => {
            const isPaused = equalizerWrapper.classList.toggle("paused");

            if (playIcon && pauseIcon) {
                if (isPaused) {
                    playIcon.classList.remove("hidden");
                    pauseIcon.classList.add("hidden");
                    previewPlayBtn.setAttribute("aria-label", "Resume visual equalizer animation");
                } else {
                    playIcon.classList.add("hidden");
                    pauseIcon.classList.remove("hidden");
                    previewPlayBtn.setAttribute("aria-label", "Pause visual equalizer animation");
                }
            }
        });
    }

    // 3. Interactive Mood Card Selection Preview
    const moodCards = document.querySelectorAll(".mood-card");
    moodCards.forEach((card) => {
        // Click interaction
        card.addEventListener("click", () => {
            moodCards.forEach((c) => c.classList.remove("active"));
            card.classList.add("active");
        });

        // Keyboard accessibility (Enter or Space)
        card.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                moodCards.forEach((c) => c.classList.remove("active"));
                card.classList.add("active");
            }
        });
    });

    // 4. Interactive Language Pill Selection Preview
    const langPills = document.querySelectorAll(".lang-pill");
    langPills.forEach((pill) => {
        pill.addEventListener("click", () => {
            pill.classList.toggle("active");
        });
    });

    // 5. Smooth Scroll for Internal Anchor Links
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener("click", (event) => {
            const targetId = anchor.getAttribute("href");
            if (targetId && targetId !== "#" && targetId.length > 1) {
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    event.preventDefault();
                    targetElement.scrollIntoView({
                        behavior: "smooth",
                        block: "start"
                    });
                }
            }
        });
    });
});
