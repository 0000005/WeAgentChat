const navToggle = document.querySelector(".nav-toggle");
const navDrawer = document.querySelector("[data-drawer]");

if (navToggle && navDrawer) {
  navToggle.addEventListener("click", () => {
    navDrawer.classList.toggle("open");
    navToggle.setAttribute(
      "aria-expanded",
      navDrawer.classList.contains("open").toString()
    );
  });

  navDrawer.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      navDrawer.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
    });
  });
}

const prefersReducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)"
).matches;

const revealElements = document.querySelectorAll(".reveal");
if (!prefersReducedMotion && revealElements.length) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.2 }
  );

  revealElements.forEach((el) => revealObserver.observe(el));
} else {
  revealElements.forEach((el) => el.classList.add("in-view"));
}

const carouselTrack = document.querySelector("[data-carousel]");
const prevBtn = document.querySelector(".carousel-btn.prev");
const nextBtn = document.querySelector(".carousel-btn.next");

if (carouselTrack) {
  const items = carouselTrack.querySelectorAll(".carousel-item");
  const dotsContainer = document.querySelector("[data-dots]");
  let index = 0;

  // Clear and regenerate dots if container exists
  if (dotsContainer) {
    dotsContainer.innerHTML = "";
    items.forEach((_, i) => {
      const dot = document.createElement("button");
      dot.className = "dot" + (i === 0 ? " active" : "");
      dot.setAttribute("aria-label", `第 ${i + 1} 张`);
      dot.addEventListener("click", () => updateCarousel(i));
      dotsContainer.appendChild(dot);
    });
  }

  const allDots = dotsContainer?.querySelectorAll(".dot") || [];

  const updateCarousel = (nextIndex) => {
    index = (nextIndex + items.length) % items.length;
    carouselTrack.style.transform = `translateX(-${index * 100}%)`;
    allDots.forEach((dot, dotIndex) => {
      dot.classList.toggle("active", dotIndex === index);
    });
  };

  prevBtn?.addEventListener("click", () => updateCarousel(index - 1));
  nextBtn?.addEventListener("click", () => updateCarousel(index + 1));

  // Handle swipes for touch devices
  let startX = 0;
  carouselTrack.addEventListener("touchstart", (e) => (startX = e.touches[0].clientX));
  carouselTrack.addEventListener("touchend", (e) => {
    const endX = e.changedTouches[0].clientX;
    if (startX - endX > 50) updateCarousel(index + 1);
    else if (endX - startX > 50) updateCarousel(index - 1);
  });

  updateCarousel(0);
}

// Lightbox functionality
const lightbox = document.getElementById("lightbox");
const lightboxImg = document.getElementById("lightboxImg");
const lightboxClose = document.querySelector(".lightbox-close");

if (lightbox && lightboxImg) {
  // Open lightbox when clicking carousel images
  document.querySelectorAll(".carousel-item img").forEach((img) => {
    img.addEventListener("click", () => {
      lightboxImg.src = img.src;
      lightboxImg.alt = img.alt;
      lightbox.classList.add("active");
      lightbox.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    });
  });

  // Close lightbox
  const closeLightbox = () => {
    lightbox.classList.remove("active");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  lightboxClose?.addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  // Close on ESC key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && lightbox.classList.contains("active")) {
      closeLightbox();
    }
  });
}
