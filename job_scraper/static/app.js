document.querySelectorAll(".toggle-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const id = btn.dataset.id;
    const response = await fetch(`/jobs/${id}/toggle`, { method: "POST" });
    if (!response.ok) return;
    const data = await response.json();
    const row = document.getElementById(`job-${id}`);
    row.classList.toggle("applied", data.is_applied);
    btn.textContent = data.is_applied ? "Applied ✓" : "Mark applied";
  });
});
