# SkellyClicker documentation site

This site uses the shared SkellyDocs theme and Docusaurus. Use Node.js 24 and run these commands from this directory.

```sh
npm ci
npm start
```

Open [the local preview](http://localhost:3000/skellyclicker/). Edit pages in `docs/` to see changes in the preview.

To check types, build the static site and preview the build locally, run:

```sh
npm run typecheck
npm run build
npm run serve
```

The production files are written to `build/`. The sidebar picks up new Markdown or MDX pages automatically. Set `sidebar_position` in each page’s front matter to order a guide. Add the first recording tutorial once its workflow has been verified end to end.
