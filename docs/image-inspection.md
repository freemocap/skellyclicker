# Image inspection variants

The image catalog controls thumbnail size and selects either target crop or full image. These controls change presentation only, never dataset membership or labels. Raw and annotated variants identify the same camera image and label-manifest revision.

`GET /api/labels/thumbnail` accepts `project_path`, `label_manifest_sha256`, `image_id`, `crop` (default true), `annotated` (default true), and `max_size` (64–1024, default320). Crop bounds come from the existing published target projection and are identical for raw and annotated variants. An unavailable target crop returns204 instead of substituting unrelated pixels. Full-image thumbnails remain available for inspecting those frames.

`GET /api/labels/image` accepts the same identity and `annotated`, and always returns full resolution without cropping. Raw mode serves the verified original PNG file. Annotated mode draws the existing mesh outline and keypoints onto a separate image buffer, preserving the original dimensions. Neither route writes source images. Stale label identities return409.

Rendering cache keys include source identity, crop bounds, annotation state and requested size. Browser responses carry stable image/version headers and private caching. Gallery consumers use bounded thumbnails; modal consumers request full-resolution variants only when opened. Switching annotation visibility must select actual corresponding raw pixels, not obscure or remove annotations with CSS.

Tests in `test_target_crops.py` verify byte-identical raw full-image responses, matching crop dimensions/pixels, full-resolution output, resized full-image aspect ratio, source immutability, stale identity rejection and size validation. They run against the ASGI route without additional environment dependencies.
