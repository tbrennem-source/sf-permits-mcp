.PHONY: help qa-launcher

## help: Show available make targets
help:
	@echo ""
	@echo "  Available targets:"
	@echo "  ─────────────────────────────────────────"
	@echo "  qa-launcher   Generate qa-drop/launcher.html from QA scripts"
	@echo "  help          Show this help message"
	@echo ""

## qa-launcher: Generate qa-drop/launcher.html with copy buttons for each QA script
qa-launcher:
	@python3 scripts/gen_qa_launcher.py
