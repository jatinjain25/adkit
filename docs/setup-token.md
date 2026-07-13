# Getting a Meta token and linking Instagram

adkit talks to the Meta Marketing API on your behalf. You need three things: an
app, an access token with the right scopes, and a Page linked to an Instagram
business account.

## 1. Create a Meta app

1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps) and
   create an app of type **Business**.
2. Add the **Marketing API** and **Facebook Login for Business** products.
3. Note the **App ID** and **App Secret**. Put them in `.env` as `META_APP_ID`
   and `META_APP_SECRET`.

## 2. Get a token with the right scopes

Use the Graph API Explorer, or a system user in Business Settings for something
longer-lived. The token needs these scopes:

```
ads_management, ads_read, business_management,
pages_show_list, pages_read_engagement, pages_manage_ads,
pages_manage_posts, pages_manage_metadata,
instagram_basic, instagram_content_publish
```

Put the token in `.env` as `META_ACCESS_TOKEN`. A system-user token from
Business Settings does not expire and is the best option for automation.

## 3. Link Instagram (the step people miss)

Your Facebook Page must be linked to an Instagram business or creator account,
or Instagram placements and IG-actor creatives will fail.

Page Settings, then **Linked accounts**, then **Instagram**, then **Connect**.

## 4. Fill in the account and Page

- `META_AD_ACCOUNT_ID`: your ad account, bare id or `act_` prefixed.
- `META_PAGE_ID`: the Page behind your ads.
- `META_INSTAGRAM_ACTOR_ID`: the linked IG account id.

## 5. Verify

```bash
adkit verify
```

It reports token validity, the scopes present (and any missing), whether the
Page is linked to Instagram, and the ad account status. Fix anything it flags
before you build campaigns.
