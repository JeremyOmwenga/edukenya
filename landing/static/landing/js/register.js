// Live preview of the school web address while typing. Purely cosmetic:
// the server validates and normalises the subdomain itself.
(function () {
  var input = document.getElementById("id_subdomain");
  var preview = document.querySelector("[data-subdomain-preview]");
  if (!input || !preview) return;
  input.addEventListener("input", function () {
    var v = input.value.toLowerCase().replace(/[^a-z0-9-]/g, "");
    preview.textContent = v || "yourschool";
  });
})();
