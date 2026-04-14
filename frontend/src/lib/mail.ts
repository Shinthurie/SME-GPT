import nodemailer from "nodemailer";

const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  port: Number(process.env.SMTP_PORT || 587),
  secure: false,
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS,
  },
});

export async function sendResetPasswordEmail(to: string, resetLink: string) {
  await transporter.sendMail({
    from: process.env.MAIL_FROM,
    to,
    subject: "Reset your SME-GPT password",
    html: `
      <div style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2>Reset Your Password</h2>
        <p>We received a request to reset your SME-GPT password.</p>
        <p>Click the button below to create a new password:</p>
        <p>
          <a href="${resetLink}" style="display:inline-block;padding:12px 20px;background:#07122f;color:#ffffff;text-decoration:none;border-radius:10px;">
            Reset Password
          </a>
        </p>
        <p>If the button does not work, use this link:</p>
        <p>${resetLink}</p>
        <p>This link will expire in 30 minutes.</p>
      </div>
    `,
  });
}

export async function sendLoginVerificationEmail(
  to: string,
  confirmLink: string,
  trustLink: string
) {
  await transporter.sendMail({
    from: process.env.MAIL_FROM,
    to,
    subject: "Verify your SME-GPT login",
    html: `
      <div style="font-family: Arial, sans-serif; line-height: 1.6;">
        <h2>New Login Attempt</h2>
        <p>We detected a login from a new device.</p>
        <p>You can choose one of the options below:</p>

        <p>
          <a href="${confirmLink}" style="display:inline-block;padding:12px 20px;background:#07122f;color:#ffffff;text-decoration:none;border-radius:10px;margin-right:8px;">
            Confirm Login
          </a>
        </p>

        <p>
          <a href="${trustLink}" style="display:inline-block;padding:12px 20px;background:#2563ff;color:#ffffff;text-decoration:none;border-radius:10px;">
            Trust This Device
          </a>
        </p>

        <p>If you did not request this login, ignore this email.</p>
        <p>This link expires in 15 minutes.</p>
      </div>
    `,
  });
}