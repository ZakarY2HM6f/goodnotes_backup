const target = document.body;

const intercept_downloads = (mutationList, _) => {
  for (const mutation of mutationList) {
    if (mutation.type === "childList") {
        if (mutation.addedNodes.length <= 0) continue;
        if (mutation.addedNodes[0].tagName != 'A') continue;

        const a =  mutation.addedNodes[0];
        a.addEventListener('click', (e) => e.preventDefault());

        const sd = document.createElement("selenium-data");
        sd.href = a.href;
        sd.setAttribute("download", a.getAttribute("download"));
        sd.style.display = 'none';
        setTimeout(() => document.body.appendChild(sd));
    }}
};

const observer = new MutationObserver(intercept_downloads);
observer.observe(target, {childList: true});
