# Code Notes

This file is for code snippets and explanations to remember. It is not imported or used by the project.

## 1. Displaying a Unicode character accessibly

```jsx
<span aria-hidden="true">{String.fromCodePoint(0x26a1)}</span>{" "}
```

- `String.fromCodePoint(0x26a1)` converts the Unicode code point `0x26a1` into the ⚡ character.
- `<span>` wraps the character so it can be styled or targeted separately.
- `aria-hidden="true"` tells screen readers to ignore this decorative icon, preventing an unnecessary spoken symbol.
- `{" "}` adds an explicit space in JSX between the icon and the following text. JSX does not preserve whitespace in every spot as plain HTML text might.

## 2. Styling a file input with a label

```jsx
<label className="upload-label" htmlFor="photo-upload">
  <span className="upload-icon" aria-hidden="true">↑</span>
  <span>
    <strong>Choose a photo</strong>
    <small>JPG, PNG, WebP or another browser-supported image</small>
  </span>
</label>
```

- The `<label>` presents the upload control as a styled, clickable area with the prompt and supported image formats.
- `htmlFor="photo-upload"` associates this label with the file input whose `id` is `photo-upload`. In React, `htmlFor` is used instead of the HTML attribute `for`.
- Because the input has that matching `id`, clicking the label opens the browser's file picker, and assistive technology can identify the label as the input's name.
- The upward arrow is decorative, so `aria-hidden="true"` keeps screen readers from announcing it separately.

## 3. Complete flow of `Editor.jsx`

`Editor` is a React function component that displays an image upload area, an original-image preview, enhancement controls, and a placeholder for the processed result. The current version can load and preview an image, but image processing is not connected yet.

### 1. Imports and component state

```jsx
import { useEffect, useState } from "react";
import "./Editor.css";
```

- `useState` stores values that change while the user interacts with the editor. Updating state causes React to render the component again.
- `useEffect` runs a side effect when a value changes; here it manages cleanup for the temporary preview URL.
- `Editor.css` provides the component's styles.

The component creates these state values:

- `originalUrl` holds a temporary browser URL for the selected image. An empty string means there is no current image.
- `fileName` stores the selected file's name for display, the image's alternative text, and the original download name.
- `isLoading` tracks whether the preview image is still loading.
- `error` stores an error message, such as an invalid file type or a preview that failed to load.
- `notice` stores an informational message, currently used to explain that processing is not connected.
- `settings` stores the three slider values: contrast starts at 50, while noise reduction and sharpening start at 0.

### 2. Temporary preview URL cleanup

```jsx
useEffect(() => {
  if (!originalUrl) return undefined;
  return () => URL.revokeObjectURL(originalUrl);
}, [originalUrl]);
```

When `originalUrl` changes, the effect arranges to revoke the previous object URL during cleanup. Revoking it releases the browser resource created for the local file. If there is no URL, there is nothing to clean up.

### 3. Selecting and validating a file

The upload input is a file picker:

```jsx
<input
  id="photo-upload"
  className="file-input"
  type="file"
  accept="image/*"
  onChange={handleFileChange}
/>
```

`accept="image/*"` hints that the picker should show image files. The `onChange` handler runs after the user chooses a file. It:

1. Reads the first selected file from `event.target.files` (using optional chaining in case the list is missing).
2. Clears previous errors and notices, removes the old preview URL and file name, and resets the loading flag.
3. Stops if no file was selected.
4. Checks whether the MIME type starts with `image/`. If not, it sets an error message, clears the input value so the same file can be selected again, and stops.
5. Creates a local object URL with `URL.createObjectURL(file)`, stores it and the file name in state, and marks the preview as loading.

The upload label and input are connected through `htmlFor="photo-upload"` and `id="photo-upload"`, so clicking the styled label opens the picker.

### 4. Rendering the editor layout

The returned JSX is the editor's visible interface:

- The outer `<section>` is named by the heading with `aria-labelledby="editor-title"`.
- The heading explains that the user can upload an image and preview the original.
- The upload area shows the clickable label. Once a file is selected, a conditional message displays its name.
- If `error` contains text, an error paragraph appears with `role="alert"`, which helps assistive technology announce it promptly.
- If `notice` contains text, a status paragraph appears with `role="status"`.
- The workspace contains three panels: the original preview, enhancement controls, and the enhanced-result placeholder.

### 5. Showing the original preview

If `originalUrl` exists, the preview panel renders an `<img>` using that URL and gives it alternative text containing the file name. Its `onLoad` handler clears the loading state. Its `onError` handler clears loading and sets an error message if the browser cannot display the image.

While the image is loading, a loading message is shown over the preview area. If there is no selected image, the panel instead prompts the user to choose a photo.

### 6. Downloading the original

`handleDownloadOriginal` first checks that an image URL exists. It then creates a temporary anchor element, points it at the original URL, sets its download name to the file name (or `original-image` as a fallback), and programmatically clicks it. The download button is disabled when there is no image or while the preview is loading.

### 7. Updating enhancement sliders

Each range input has a `name` matching a key in `settings`. When a slider changes, `handleSettingChange` reads its name and value, converts the value from a string to a number, and updates only that setting:

```jsx
setSettings((current) => ({ ...current, [name]: Number(value) }));
```

The functional update uses the latest state, and the spread (`...current`) keeps the other settings unchanged. Each slider displays its current value as a percentage. The controls are disabled until an image has been selected.

### 8. Processing and result panel

`handleProcess` currently sets a notice saying processing is not connected and that the original has not changed. It does not apply the slider values or create an enhanced image. The Process image button is disabled without a selected image or while its preview is loading.

The enhanced-result panel currently displays a placeholder message, and its download button is disabled because no processed result exists yet.

### Overall interaction

The user chooses a photo, the component validates it, and the browser displays a local preview. The user can download that original and adjust the three settings. The processing button currently explains that enhancement is not available; once an image-processing service is connected, that handler and the result panel would need to use its output.
