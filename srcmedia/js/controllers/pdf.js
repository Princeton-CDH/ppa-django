class PdfController extends window.StimulusModule.Controller {
  static targets = [
        "downloadFinal",
        "downloadPreview",
        "final",
        "heading",
        "preview",
    ];
    static values = { apikey: String, url: String };

    connect() {
        // if no published URL is present, disable functions and show message
        if (!this.urlValue) {
            this.headingTarget.innerHTML = "Publish this page to enable PDF generation.";
            this.previewTarget.disabled = true;
            this.finalTarget.disabled = true;
        }
    }

    async generatePdf(evt) {
        // use the DocRaptor API to generate a PDF of the published editorial
        const isPreview = evt.target === this.previewTarget;
        const downloadTarget = isPreview ? this.downloadPreviewTarget : this.downloadFinalTarget;

        // set loading state
        this.previewTarget.disabled = true;
        this.finalTarget.disabled = true;
        downloadTarget.innerText = "Loading...";

        try {
            // attempt API fetch
            const res = await fetch("https://api.docraptor.com/docs", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    user_credentials: this.apikeyValue,
                    doc: {
                        test: isPreview,
                        document_type: "pdf",
                        document_url:  this.urlValue,
                    }
                }),
            });
            if (!res.ok) {
                // DocRaptor returns errors as UTF-8 text
                const errorText = await res.text();
                throw new Error(`Error: ${errorText}`);
            }
            // download PDF binary response as a blob, create a URL for it, and show link
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const downloadLink = document.createElement("a");
            downloadLink.href = url;
            downloadLink.download = isPreview ? "preview.pdf" : "final.pdf";
            downloadLink.textContent = "Download PDF";
            downloadTarget.innerText = "";
            downloadTarget.appendChild(downloadLink);
        } catch(error) {
            // show error msg to user
            downloadTarget.innerText = error.message;
        }

        // stop loading state
        this.previewTarget.disabled = false;
        this.finalTarget.disabled = false;
    }
}

// register with wagtail
window.wagtail.app.register('pdf', PdfController);
