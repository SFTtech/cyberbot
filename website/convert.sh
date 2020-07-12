pandoc \
    --standalone \
    -i src/index.md \
    -f gfm \
    -o public/index.html \
    -t html5 \
    --metadata title="Cyberbot" \
    -c "style.css"
