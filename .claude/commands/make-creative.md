---
description: Generate an ad creative (image or video) with adkit, cost-aware
---

The user wants an ad creative. Their request:

$ARGUMENTS

Do this:

1. Turn the request into a strong, specific image or video prompt (subject,
   setting, lighting, composition, on-brand palette, any headline text to render).
2. Tell the user the estimated cost: images are ~$0.15, videos ~$0.60 to $1.20
   depending on duration. Wait for a plain "go".
3. For an image: `adkit generate image "PROMPT" --out creatives/<slug>.png --aspect 1:1`
   (use 9:16 for Stories/Reels, 4:5 or 1:1 for feed).
   For a video: draft a Fast version first with
   `adkit generate video "PROMPT" --out creatives/<slug>.mp4 --duration 8`.
4. Report the saved path and the running total from `adkit generate spend`.
5. Only regenerate variations after the user approves the draft and the extra cost.
