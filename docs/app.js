function setupCopyButtons() {
  const buttons = document.querySelectorAll(".copy-btn");
  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const targetId = button.getAttribute("data-copy-target");
      const node = targetId ? document.getElementById(targetId) : null;
      if (!node) {
        return;
      }

      const text = node.textContent || "";
      try {
        await navigator.clipboard.writeText(text.trim());
        const original = button.textContent;
        button.textContent = "已复制";
        setTimeout(() => {
          button.textContent = original;
        }, 1200);
      } catch (_) {
        button.textContent = "复制失败";
        setTimeout(() => {
          button.textContent = "复制";
        }, 1200);
      }
    });
  });
}

function setupReveal() {
  const revealBlocks = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    revealBlocks.forEach((node) => node.classList.add("in-view"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.16 }
  );

  revealBlocks.forEach((node) => observer.observe(node));
}

setupCopyButtons();
setupReveal();
