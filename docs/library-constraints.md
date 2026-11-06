# Layer One: Library Constraints

The facts the guide depends on. Every library rule in the bot should trace back to this file.

- **Owners:** Blake Thomas (Analyst), Nick Brooks (Product Owner)
- **Last checked:** November 6, 2026, on the live UA Libraries pages
- **Policy version:** 3D Printing Guidelines, rev. 10/14/2025

**Status labels**

- **Confirmed:** stated on a UA Libraries page
- **Proposed:** our recommendation, not a library rule
- **Open:** needs an answer from library staff before we build on it

Sources are listed at the end of this file.

## 1. Printers and build volumes

Status: Confirmed, except where noted.

| Printer | Library | Max build, W x H x D | Print material | Support material | Nozzles |
| --- | --- | --- | --- | --- | --- |
| Ultimaker S5 | Bruno, Gorgas | 330 x 240 x 300 mm (13 x 9.4 x 11.8 in) | ABS, PLA | PVA | 0.25, 0.4 (default), 0.6, 0.8 mm |
| Stratasys F270 | Rodgers (3D Studio) | 305 x 254 x 305 mm (12 x 10 x 12 in) | ABS | QSR | Not listed |
| Bambu X1C | Rodgers (3D Studio) | 256 x 256 x 256 mm (about 10.1 in per side) | PLA | Not listed | 0.4 hardened steel (default); optional 0.2, 0.6, 0.8 mm |

Notes:

- UA lists the F270 as "12 x 10 x 12" with no units. The inches and mm come from the Stratasys spec sheet.
- UA lists PVA with the Ultimaker's print media. Calling it support material is our reading, based on how it is normally used.
- The Equipment page's layout makes the Bambu's location look unclear, but the fee lines say "Rodgers Bambu Printer." We treat Rodgers as correct.

## 2. Materials and colors by library

Status: Confirmed. Guidelines list colors by library, not by printer.

| Library | ABS colors | PLA colors |
| --- | --- | --- |
| Bruno | Black, blue, grey, red, white | Black, blue, green, orange, red, tough (matte black), translucent, white, yellow |
| Gorgas | Black, blue, green, grey, red, white | Black, blue, green, orange, red, translucent, white, yellow |
| Rodgers | Blue, black, red, white, ivory | Grey, white, red, green |

## 3. How the library charges

Status: Confirmed. The library charges **by weight**, using flat tiers up to 120 g and a per-gram rate above that. Fees are per print job, not per object.

| Tier | Ultimaker S5 (Bruno, Gorgas) | Bambu X1C (Rodgers) | Stratasys F270 (Rodgers) |
| --- | --- | --- | --- |
| Small: 30 g or less | $3 | $3 | $5 |
| Medium: 31 to 61 g | $6 | $6 | $10 |
| Large: up to 120 g | $11 | $11 | $20 |
| Very large: custom | grams x $0.09 | grams x $0.09 | grams x $0.16 |
| Plate fee | None listed | Unclear (see Q1) | $8 per job |

Other fee rules:

- There are no academic waivers or discounts.
- Payment is by BamaCash or Departmental Transfer only.
- Printing doesn't start until payment is received.
- Failed prints are refunded for equipment failure, not for file errors.

## 4. Prohibited items

Status: Confirmed. Guidelines wording:

> Users may 3D print any object for research and education with the following exceptions:
>
> - No weapons, weapon accessories, or weapon components;
> - No objects that resemble weapons or weapon accessories;
> - No illegal objects; and
> - No copyrighted objects or any other objects that violate patents and trademarks.
> - Items such as the UA Athletics script A, images of Big Al, characters from animated series, etc. may not be printed without written approval of the copyright holder.
> - To receive permission to print UA Athletics script A, images of Big Al, etc., please contact the UA Licensing Department.
> - Items licensed under the Creative Commons mechanism may be printed if the use is authorized by the particular license.
> - Nothing may be printed for commercial purposes.
> - No objects may be printed that others might find offensive.

Safety-critical parts are **not** on this list. Declining them is our own guardrail, from the SOW.

## 5. Approved model sites

Status: **Proposed. No approved list exists.** The library's 3D Print page lists these under "Model Repositories" but doesn't call them approved.

| Site | What it is | Proposal for the bot |
| --- | --- | --- |
| Thingiverse | Model library | Candidate for search |
| GrabCAD | CAD model library | Candidate for search |
| Yeggi | Search engine across other sites | Exclude: results come from sites we haven't reviewed |
| Google | General web search | Exclude: results can't be screened |

Before anything is final:

- Ethan confirms that each candidate offers usable API access and license data. We have not verified this.
- Nick asks staff whether they object to the list.

## 6. Submission process

Status: Confirmed. Students use the [3D print request form](https://bama.atlassian.net/servicedesk/customer/portal/179).

1. **Submit:** The student uploads STL files through the form. **Only STL is accepted**, even though some printer software reads other formats.
2. **Fill in the form:** Required fields include name, UA email, project title, preferred library (this sets the pickup location), and payment method.
3. **Add details:** The form also has a class or personal request type, a source URL for downloaded files, and a notes box. Staff use the source link to review the creator's print recommendations.
4. **Review:** Staff review the design, then email approval and the cost.
5. **Pay:** The student comes in to sign and pay, or a Departmental Transfer is approved.
6. **Print:** The job enters a first-in, first-out queue. Staff run all jobs.
7. **Pick up:** The student gets an email and picks up at the circulation desk of the library where they submitted.

Timing and limits:

- Guidelines allow up to 2 weeks at Bruno and Gorgas in high demand, and up to 3 weeks at Rodgers.
- During busy times, a job may be printed at another library, but pickup doesn't change.
- Service is for current UA faculty, staff, and students.
- Students without an STL file are directed to "Ask a Question" or to a library.
- Designs that Bruno or Gorgas can't print well may be referred to The Cube.

**Contacts**

| Library | Email | Phone |
| --- | --- | --- |
| Bruno | 3dbruno@ua.edu | (205) 348-1086 |
| Gorgas | 3dlib@ua.edu | (205) 348-9748 |
| Rodgers | 3drodgers@ua.edu | (205) 348-2100 |

## 7. How the bot uses this

Status: Proposed. These rules turn the facts above into logic for the AI lane.

### Request allowed?

| Request | Bot action |
| --- | --- |
| Weapon, weapon part, accessory, or lookalike | Decline |
| Illegal object | Decline |
| Copyrighted, patented, or trademarked object | Decline |
| UA Athletics script A or Big Al | Decline and refer to UA Licensing |
| Printing for commercial purposes | Decline |
| Safety-critical part (our guardrail) | Decline and give the safety warning |
| Might be offensive | Route to staff, because the rule depends on judgment |
| Creative Commons model | Allow only if the license authorizes the use |
| Missing or unclear license | Route to staff |

### Check size and printer fit

1. Require STL for the final file.
2. Compare the model's dimensions with each printer in Section 1.
3. Sort both sets of dimensions before comparing, because staff can rotate a model.
4. If it fits no printer, route the student to staff.
5. If the student needs a certain material or color, filter by library using Section 2.

Fit doesn't guarantee that a model will print well, so the bot says "fits the printer," never "will print."

### Cost estimate

1. Estimate grams from the model.
2. Apply the tier for the printer.
3. Add the plate fee for Stratasys jobs.
4. Show the result as an estimate, and say staff set the final cost.

Until staff answer Q2, treat 61 g as Medium. Anything above 120 g uses the per-gram rate.

Test cases, using the rules above:

| Weight | Ultimaker S5 | Bambu X1C (no plate fee assumed) | Stratasys F270, with plate fee |
| --- | --- | --- | --- |
| 25 g | $3.00 | $3.00 | $13.00 |
| 45 g | $6.00 | $6.00 | $18.00 |
| 100 g | $11.00 | $11.00 | $28.00 |
| 200 g | $18.00 | $18.00 | $40.00 |

## 8. Questions for library staff

Status: Open. Nick to ask through the form's "Ask a Question" option.

| # | Question | Why it matters |
| --- | --- | --- |
| Q1 | Does the $8 plate fee apply to the Bambu? The line says "all print jobs," but it sits in the Stratasys pricing. | Changes a Bambu estimate by $8 |
| Q2 | Is exactly 61 g Medium or Large on the Ultimaker and Bambu? Both tiers include 61. | Changes the tier result |
| Q3 | At Rodgers, who picks the printer? The form asks for a library, not a printer. | A 25 g job is $3 on the Bambu and $13 on the Stratasys |
| Q4 | What infill and support settings do staff normally use? | The bot can't estimate grams accurately without them |
| Q5 | Do you object to Thingiverse and GrabCAD as the bot's search sites? | Finalizes Section 5 |
| Q6 | Is the Bambu missing from the form's fee list by mistake? | The 3D Print page and Guidelines both list its pricing |
| Q7 | Is ABS at Rodgers Stratasys-only, and PLA Bambu-only? | The pages imply this but don't state it |
| Q8 | What usually triggers an "offensive" rejection? | Helps the bot know when to route to staff |

## Sources

- [3D Print page](https://www.lib.ua.edu/using-the-library/3d-print/), UA Libraries
- [3D Printing Guidelines](https://www.lib.ua.edu/about/libraries-policies/3d-printing-guidelines/), UA Libraries, rev. 10/14/2025
- [Equipment page](https://www.lib.ua.edu/using-the-library/equipment/), UA Libraries
- [3D print request form](https://bama.atlassian.net/servicedesk/customer/portal/179/group/449/create/1314), UA Libraries service desk
- [F123 Series spec sheet](https://stratasys-corporate-prod-slot.dxc.stratasys.com/siteassets/3d-printers/printer-catalog/fdm-printers/f123-series-printers/pss_fdm_f123series_0721a-1-1.pdf), Stratasys, used for F270 dimensions only
